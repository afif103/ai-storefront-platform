"""M7 P2 — Notification services + Celery tasks tests."""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.donation import Donation
from app.models.notification_preference import NotificationPreference
from app.models.order import Order
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.models.tenant_member import TenantMember
from app.services.notifications.email_sender import send_email
from app.services.notifications.telegram_sender import send_telegram
from app.services.notifications.templates import (
    format_donation_notification,
    format_order_notification,
)
from app.workers.tasks.notifications import (
    _process_donation_notification,
    _process_order_notification,
)

pytestmark = pytest.mark.m7


# ---- Helpers ----


async def _seed_tenant_with_prefs(
    db: AsyncSession,
    *,
    email_enabled: bool = False,
    telegram_enabled: bool = False,
    telegram_chat_id: str | None = None,
) -> tuple[Tenant, NotificationPreference]:
    """Create a plan, tenant, owner user, membership, and notification prefs."""
    uid = uuid.uuid4().hex[:8]

    plan = Plan(name=f"Plan {uid}", ai_token_quota=1000, max_members=5)
    db.add(plan)
    await db.flush()

    tenant = Tenant(name=f"Tenant {uid}", slug=f"t-{uid}", plan_id=plan.id)
    db.add(tenant)
    await db.flush()

    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant.id)},
    )

    prefs = NotificationPreference(
        tenant_id=tenant.id,
        email_enabled=email_enabled,
        telegram_enabled=telegram_enabled,
        telegram_chat_id=telegram_chat_id,
    )
    db.add(prefs)
    await db.flush()

    return tenant, prefs


async def _seed_order(
    db: AsyncSession,
    tenant: Tenant,
    *,
    customer_email: str | None = "customer@test.com",
) -> Order:
    uid = uuid.uuid4().hex[:8]
    order = Order(
        tenant_id=tenant.id,
        order_number=f"ORD-{uid}",
        customer_name="Test Customer",
        customer_email=customer_email,
        items=[{"name": "Widget", "qty": 1, "unit_price": "5.000", "subtotal": "5.000"}],
        total_amount=Decimal("5.000"),
        currency="KWD",
        status="pending",
    )
    db.add(order)
    await db.flush()
    return order


async def _seed_donation(
    db: AsyncSession,
    tenant: Tenant,
    *,
    donor_email: str | None = "donor@test.com",
) -> Donation:
    uid = uuid.uuid4().hex[:8]
    donation = Donation(
        tenant_id=tenant.id,
        donation_number=f"DON-{uid}",
        donor_name="Test Donor",
        donor_email=donor_email,
        amount=Decimal("10.000"),
        currency="KWD",
        status="pending",
    )
    db.add(donation)
    await db.flush()
    return donation


# ---- Template tests ----


def test_format_order_notification():
    subject, body = format_order_notification(
        tenant_name="My Store",
        order_number="ORD-00001",
        total="5.000",
        currency="KWD",
        customer_name="Alice",
    )
    assert "My Store" in subject
    assert "ORD-00001" in subject
    assert "ORD-00001" in body
    assert "Alice" in body
    assert "5.000 KWD" in body


def test_format_donation_notification():
    subject, body = format_donation_notification(
        tenant_name="My Charity",
        donation_number="DON-00001",
        amount="10.000",
        currency="KWD",
        donor_name="Bob",
    )
    assert "My Charity" in subject
    assert "DON-00001" in subject
    assert "Bob" in body
    assert "10.000 KWD" in body


# ---- Email sender tests ----


@patch("app.services.notifications.email_sender.settings")
def test_email_sender_dev_mode(mock_settings):
    """Dev mode logs instead of sending."""
    mock_settings.ENVIRONMENT = "development"
    result = send_email(to="a@b.com", subject="Test", body="Hello")
    assert result is True


@patch("app.services.notifications.email_sender.boto3")
@patch("app.services.notifications.email_sender.settings")
def test_email_sender_prod_mode(mock_settings, mock_boto3):
    """Prod mode calls SES."""
    mock_settings.ENVIRONMENT = "production"
    mock_settings.SES_REGION = "me-south-1"
    mock_settings.SES_SENDER_EMAIL = "noreply@test.com"
    mock_ses = MagicMock()
    mock_boto3.client.return_value = mock_ses

    result = send_email(to="user@test.com", subject="Subj", body="Body")

    assert result is True
    mock_boto3.client.assert_called_once_with("ses", region_name="me-south-1")
    mock_ses.send_email.assert_called_once()
    call_kwargs = mock_ses.send_email.call_args[1]
    assert call_kwargs["Source"] == "noreply@test.com"
    assert call_kwargs["Destination"]["ToAddresses"] == ["user@test.com"]


# ---- Telegram sender tests ----


@patch("app.services.notifications.telegram_sender.httpx.post")
def test_telegram_sender_success(mock_post):
    """Successful Telegram send."""
    mock_post.return_value = MagicMock(status_code=200)
    result = send_telegram(bot_token="tok123", chat_id="-100999", text="Hello")

    assert result is True
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "tok123" in call_args[0][0]  # URL contains token
    assert call_args[1]["json"]["chat_id"] == "-100999"


@patch("app.services.notifications.telegram_sender.httpx.post")
def test_telegram_sender_api_error(mock_post):
    """Telegram API returns error — logs and returns False."""
    mock_post.return_value = MagicMock(status_code=400, text="Bad Request")
    result = send_telegram(bot_token="tok123", chat_id="-100999", text="Hello")
    assert result is False


def test_telegram_sender_empty_token():
    """Empty bot token — skips safely."""
    result = send_telegram(bot_token="", chat_id="-100999", text="Hello")
    assert result is False


def test_telegram_sender_empty_chat_id():
    """Empty chat_id — skips safely."""
    result = send_telegram(bot_token="tok123", chat_id="", text="Hello")
    assert result is False


# ---- Celery task tests (async helpers, mocked senders) ----


@patch("app.workers.tasks.notifications.send_telegram")
@patch("app.workers.tasks.notifications.send_email")
async def test_order_notification_both_enabled(
    mock_email: MagicMock, mock_tg: MagicMock, db: AsyncSession
):
    """Both channels enabled — both senders called."""
    mock_email.return_value = True
    mock_tg.return_value = True

    tenant, _ = await _seed_tenant_with_prefs(
        db, email_enabled=True, telegram_enabled=True, telegram_chat_id="-100"
    )
    order = await _seed_order(db, tenant)
    await db.flush()

    await _process_order_notification(db, str(tenant.id), str(order.id))

    mock_email.assert_called_once()
    assert mock_email.call_args[1]["to"] == "customer@test.com"
    mock_tg.assert_called_once()
    assert mock_tg.call_args[1]["chat_id"] == "-100"


@patch("app.workers.tasks.notifications.send_telegram")
@patch("app.workers.tasks.notifications.send_email")
async def test_order_notification_both_disabled(
    mock_email: MagicMock, mock_tg: MagicMock, db: AsyncSession
):
    """Both channels disabled — neither sender called."""
    tenant, _ = await _seed_tenant_with_prefs(db)
    order = await _seed_order(db, tenant)
    await db.flush()

    await _process_order_notification(db, str(tenant.id), str(order.id))

    mock_email.assert_not_called()
    mock_tg.assert_not_called()


@patch("app.workers.tasks.notifications.send_telegram")
@patch("app.workers.tasks.notifications.send_email")
async def test_donation_notification_email_only(
    mock_email: MagicMock, mock_tg: MagicMock, db: AsyncSession
):
    """Email enabled, Telegram disabled — only email sender called."""
    mock_email.return_value = True

    tenant, _ = await _seed_tenant_with_prefs(db, email_enabled=True)
    donation = await _seed_donation(db, tenant)
    await db.flush()

    await _process_donation_notification(db, str(tenant.id), str(donation.id))

    mock_email.assert_called_once()
    assert mock_email.call_args[1]["to"] == "donor@test.com"
    mock_tg.assert_not_called()


@patch("app.workers.tasks.notifications.send_telegram")
@patch("app.workers.tasks.notifications.send_email")
async def test_order_notification_telegram_enabled_no_chat_id(
    mock_email: MagicMock, mock_tg: MagicMock, db: AsyncSession
):
    """Telegram enabled but chat_id missing — telegram skipped, email still sent."""
    mock_email.return_value = True

    tenant, _ = await _seed_tenant_with_prefs(
        db, email_enabled=True, telegram_enabled=True, telegram_chat_id=None
    )
    order = await _seed_order(db, tenant)
    await db.flush()

    await _process_order_notification(db, str(tenant.id), str(order.id))

    mock_email.assert_called_once()
    mock_tg.assert_not_called()


@patch("app.workers.tasks.notifications.send_telegram")
@patch("app.workers.tasks.notifications.send_email")
async def test_order_notification_no_customer_email(
    mock_email: MagicMock, mock_tg: MagicMock, db: AsyncSession
):
    """Email enabled but order has no customer_email — email skipped safely."""
    mock_tg.return_value = True

    tenant, _ = await _seed_tenant_with_prefs(
        db, email_enabled=True, telegram_enabled=True, telegram_chat_id="-100"
    )
    order = await _seed_order(db, tenant, customer_email=None)
    await db.flush()

    await _process_order_notification(db, str(tenant.id), str(order.id))

    mock_email.assert_not_called()
    mock_tg.assert_called_once()


@patch("app.workers.tasks.notifications.send_telegram")
@patch("app.workers.tasks.notifications.send_email")
async def test_donation_notification_no_donor_email(
    mock_email: MagicMock, mock_tg: MagicMock, db: AsyncSession
):
    """Email enabled but donation has no donor_email — email skipped safely."""
    mock_tg.return_value = True

    tenant, _ = await _seed_tenant_with_prefs(
        db, email_enabled=True, telegram_enabled=True, telegram_chat_id="-100"
    )
    donation = await _seed_donation(db, tenant, donor_email=None)
    await db.flush()

    await _process_donation_notification(db, str(tenant.id), str(donation.id))

    mock_email.assert_not_called()
    mock_tg.assert_called_once()
