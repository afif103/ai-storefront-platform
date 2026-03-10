"""M7 P1 — Notification preferences integration tests."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_preference import NotificationPreference
from app.models.tenant_member import TenantMember
from app.models.user import User
from tests.conftest import auth_headers

pytestmark = pytest.mark.m7

BASE = "/api/v1/tenants/me/notification-preferences"


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _create_tenant(client: AsyncClient, uid: str) -> tuple[dict, str]:
    """Create tenant via API, return (auth_headers, tenant_id)."""
    sub = f"np-owner-{uid}"
    email = f"np-owner-{uid}@test.com"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"NP Tenant {uid}", "slug": f"np-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201
    return headers, r.json()["id"]


async def _add_member(
    client: AsyncClient,
    db: AsyncSession,
    tenant_id: str,
    role: str = "member",
) -> dict:
    """Add a member to the tenant, return auth headers with X-Tenant-Id."""
    uid = _uid()
    sub = f"np-{role}-{uid}"
    email = f"np-{role}-{uid}@test.com"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    # Auto-provision user by creating a throwaway tenant
    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"Throwaway {uid}", "slug": f"tw-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201

    # Look up user
    result = await db.execute(select(User).where(User.cognito_sub == sub))
    user = result.scalar_one()

    # Insert active membership in target tenant
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    member = TenantMember(
        tenant_id=uuid.UUID(tenant_id),
        user_id=user.id,
        role=role,
        status="active",
        joined_at=datetime.now(UTC),
    )
    db.add(member)
    await db.commit()

    # Include X-Tenant-Id so get_db_with_tenant resolves to the right tenant
    headers["X-Tenant-Id"] = tenant_id
    return headers


# ---- GET: auto-create default ----


async def test_get_auto_creates_default(client: AsyncClient):
    """First GET creates a default row with both disabled."""
    uid = _uid()
    owner_h, _ = await _create_tenant(client, uid)

    r = await client.get(BASE, headers=owner_h)
    assert r.status_code == 200
    data = r.json()
    assert data["email_enabled"] is False
    assert data["telegram_enabled"] is False
    assert data["telegram_chat_id"] is None
    assert data["created_at"] is not None


async def test_get_is_idempotent(client: AsyncClient):
    """Second GET returns the same row, no duplicate insert."""
    uid = _uid()
    owner_h, _ = await _create_tenant(client, uid)

    r1 = await client.get(BASE, headers=owner_h)
    r2 = await client.get(BASE, headers=owner_h)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["created_at"] == r2.json()["created_at"]


# ---- PUT: partial update ----


async def test_put_updates_email_enabled(client: AsyncClient):
    """PUT can enable email notifications."""
    uid = _uid()
    owner_h, _ = await _create_tenant(client, uid)

    # Ensure default exists
    await client.get(BASE, headers=owner_h)

    r = await client.put(
        BASE,
        json={"email_enabled": True},
        headers=owner_h,
    )
    assert r.status_code == 200
    assert r.json()["email_enabled"] is True
    assert r.json()["telegram_enabled"] is False  # unchanged
    assert r.json()["updated_at"] is not None


async def test_put_updates_telegram_with_chat_id(client: AsyncClient):
    """PUT can enable Telegram when chat_id is provided."""
    uid = _uid()
    owner_h, _ = await _create_tenant(client, uid)
    await client.get(BASE, headers=owner_h)

    r = await client.put(
        BASE,
        json={"telegram_enabled": True, "telegram_chat_id": "-1001234567890"},
        headers=owner_h,
    )
    assert r.status_code == 200
    assert r.json()["telegram_enabled"] is True
    assert r.json()["telegram_chat_id"] == "-1001234567890"


async def test_put_telegram_enabled_without_chat_id_rejected(client: AsyncClient):
    """PUT rejects enabling Telegram without a chat_id."""
    uid = _uid()
    owner_h, _ = await _create_tenant(client, uid)
    await client.get(BASE, headers=owner_h)

    r = await client.put(
        BASE,
        json={"telegram_enabled": True},
        headers=owner_h,
    )
    assert r.status_code == 422


# ---- Role guards ----


async def test_member_can_get(client: AsyncClient, db: AsyncSession):
    """Member role can read notification preferences."""
    uid = _uid()
    _, tenant_id = await _create_tenant(client, uid)
    member_h = await _add_member(client, db, tenant_id, role="member")

    r = await client.get(BASE, headers=member_h)
    assert r.status_code == 200


async def test_member_cannot_put(client: AsyncClient, db: AsyncSession):
    """Member role cannot update notification preferences."""
    uid = _uid()
    owner_h, tenant_id = await _create_tenant(client, uid)
    member_h = await _add_member(client, db, tenant_id, role="member")

    # Ensure row exists
    await client.get(BASE, headers=owner_h)

    r = await client.put(
        BASE,
        json={"email_enabled": True},
        headers=member_h,
    )
    assert r.status_code == 403


async def test_admin_can_put(client: AsyncClient, db: AsyncSession):
    """Admin role can update notification preferences."""
    uid = _uid()
    _, tenant_id = await _create_tenant(client, uid)
    admin_h = await _add_member(client, db, tenant_id, role="admin")

    # Auto-create via GET
    await client.get(BASE, headers=admin_h)

    r = await client.put(
        BASE,
        json={"email_enabled": True},
        headers=admin_h,
    )
    assert r.status_code == 200
    assert r.json()["email_enabled"] is True


# ---- RLS isolation ----


async def test_rls_cross_tenant_isolation(
    rls_client: AsyncClient, db: AsyncSession
):
    """Tenant A cannot read Tenant B's notification preferences."""
    uid_a = _uid()
    uid_b = _uid()

    owner_a_h, _ = await _create_tenant(rls_client, uid_a)
    owner_b_h, _ = await _create_tenant(rls_client, uid_b)

    # Both create their prefs
    r_a = await rls_client.get(BASE, headers=owner_a_h)
    r_b = await rls_client.get(BASE, headers=owner_b_h)
    assert r_a.status_code == 200
    assert r_b.status_code == 200

    # Enable email for tenant A
    await rls_client.put(BASE, json={"email_enabled": True}, headers=owner_a_h)

    # Tenant B still sees their own defaults
    r_b2 = await rls_client.get(BASE, headers=owner_b_h)
    assert r_b2.json()["email_enabled"] is False
