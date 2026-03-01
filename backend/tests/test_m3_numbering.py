"""M3 integration tests: tenant-scoped auto-numbering for ORD/DON/PLG."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.donation import Donation
from app.models.order import Order
from app.models.plan import Plan
from app.models.pledge import Pledge
from app.models.tenant import Tenant
from app.models.tenant_member import TenantMember
from app.models.user import User
from app.services.numbering import (
    get_next_donation_number,
    get_next_order_number,
    get_next_pledge_number,
)

pytestmark = pytest.mark.m3


async def _seed_tenant(db: AsyncSession) -> uuid.UUID:
    """Create a plan + tenant + owner and return tenant_id."""
    plan = Plan(name=f"Plan-{uuid.uuid4().hex[:6]}", ai_token_quota=1000, max_members=5)
    db.add(plan)
    await db.flush()

    tenant = Tenant(
        name=f"Tenant-{uuid.uuid4().hex[:6]}",
        slug=f"t-{uuid.uuid4().hex[:8]}",
        plan_id=plan.id,
    )
    db.add(tenant)
    await db.flush()

    user = User(
        cognito_sub=f"sub-{uuid.uuid4().hex[:8]}",
        email=f"u-{uuid.uuid4().hex[:8]}@test.com",
        full_name="Test",
    )
    db.add(user)
    await db.flush()

    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant.id)},
    )

    member = TenantMember(
        tenant_id=tenant.id,
        user_id=user.id,
        role="owner",
        status="active",
        joined_at=datetime.now(UTC),
    )
    db.add(member)
    await db.flush()

    return tenant.id


# ── Order numbering ──────────────────────────────────────────────────


async def test_order_first_number(db: AsyncSession):
    """First order number for a tenant is ORD-00001."""
    tid = await _seed_tenant(db)
    num = await get_next_order_number(db, str(tid))
    assert num == "ORD-00001"


async def test_order_increments(db: AsyncSession):
    """After inserting ORD-00001, next number is ORD-00002."""
    tid = await _seed_tenant(db)

    num1 = await get_next_order_number(db, str(tid))
    assert num1 == "ORD-00001"

    order = Order(
        tenant_id=tid,
        order_number=num1,
        customer_name="Alice",
        items=[{"name": "Widget", "qty": 1, "unit_price": "5.000", "subtotal": "5.000"}],
        total_amount=Decimal("5.000"),
        status="pending",
    )
    db.add(order)
    await db.flush()

    num2 = await get_next_order_number(db, str(tid))
    assert num2 == "ORD-00002"


# ── Donation numbering ──────────────────────────────────────────────


async def test_donation_first_number(db: AsyncSession):
    """First donation number for a tenant is DON-00001."""
    tid = await _seed_tenant(db)
    num = await get_next_donation_number(db, str(tid))
    assert num == "DON-00001"


async def test_donation_increments(db: AsyncSession):
    """After inserting DON-00001, next number is DON-00002."""
    tid = await _seed_tenant(db)

    num1 = await get_next_donation_number(db, str(tid))
    assert num1 == "DON-00001"

    donation = Donation(
        tenant_id=tid,
        donation_number=num1,
        donor_name="Bob",
        amount=Decimal("10.000"),
        status="pending",
    )
    db.add(donation)
    await db.flush()

    num2 = await get_next_donation_number(db, str(tid))
    assert num2 == "DON-00002"


# ── Pledge numbering ────────────────────────────────────────────────


async def test_pledge_first_number(db: AsyncSession):
    """First pledge number for a tenant is PLG-00001."""
    tid = await _seed_tenant(db)
    num = await get_next_pledge_number(db, str(tid))
    assert num == "PLG-00001"


async def test_pledge_increments(db: AsyncSession):
    """After inserting PLG-00001, next number is PLG-00002."""
    tid = await _seed_tenant(db)

    num1 = await get_next_pledge_number(db, str(tid))
    assert num1 == "PLG-00001"

    from datetime import timedelta

    pledge = Pledge(
        tenant_id=tid,
        pledge_number=num1,
        pledgor_name="Carol",
        amount=Decimal("100.000"),
        target_date=datetime.now(UTC).date() + timedelta(days=30),
        status="pledged",
    )
    db.add(pledge)
    await db.flush()

    num2 = await get_next_pledge_number(db, str(tid))
    assert num2 == "PLG-00002"


# ── Tenant isolation ────────────────────────────────────────────────


async def test_tenant_isolation_numbering(db: AsyncSession):
    """Two tenants each start numbering at 00001 independently."""
    tid_a = await _seed_tenant(db)
    tid_b = await _seed_tenant(db)

    # Tenant A gets ORD-00001
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tid_a)},
    )
    num_a = await get_next_order_number(db, str(tid_a))
    assert num_a == "ORD-00001"

    order_a = Order(
        tenant_id=tid_a,
        order_number=num_a,
        customer_name="TenantA",
        items=[{"name": "A", "qty": 1, "unit_price": "1.000", "subtotal": "1.000"}],
        total_amount=Decimal("1.000"),
        status="pending",
    )
    db.add(order_a)
    await db.flush()

    # Tenant B also gets ORD-00001 (independent sequence)
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tid_b)},
    )
    num_b = await get_next_order_number(db, str(tid_b))
    assert num_b == "ORD-00001"

    # Tenant A next is ORD-00002
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tid_a)},
    )
    num_a2 = await get_next_order_number(db, str(tid_a))
    assert num_a2 == "ORD-00002"
