"""M6 P1 — Platform admin + tenant suspension integration tests."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from app.models.user import User
from tests.conftest import auth_headers

pytestmark = pytest.mark.m6


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _create_platform_admin(client: AsyncClient, db: AsyncSession) -> tuple[dict, str]:
    """Create a user and flag them as platform admin. Return (headers, cognito_sub).

    Uses POST /tenants/ to auto-provision the user (successful request commits).
    Then flags is_platform_admin=true directly in DB.
    """
    uid = _uid()
    sub = f"padmin-{uid}"
    email = f"padmin-{uid}@test.com"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    # Create a throwaway tenant to auto-provision the user (201 → commits)
    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"AdminOrg {uid}", "slug": f"ao-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201

    # Flag as platform admin directly in DB
    result = await db.execute(select(User).where(User.cognito_sub == sub))
    user = result.scalar_one()
    user.is_platform_admin = True
    await db.commit()

    return headers, sub


async def _create_tenant(client: AsyncClient) -> tuple[dict, str, str]:
    """Create a tenant via API. Return (owner_headers, slug, tenant_id)."""
    uid = _uid()
    sub = f"tenant-owner-{uid}"
    email = f"owner-{uid}@test.com"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"
    slug = f"t-{uid}"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"Tenant {uid}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201
    tenant_id = r.json()["id"]
    return headers, slug, tenant_id


# --- Test: Platform admin can list tenants ---


async def test_platform_admin_can_list_tenants(client: AsyncClient, db: AsyncSession):
    """Platform admin sees tenants in the list."""
    admin_headers, _ = await _create_platform_admin(client, db)
    _, slug, _ = await _create_tenant(client)

    r = await client.get("/api/v1/admin/tenants", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    slugs = [t["slug"] for t in data]
    assert slug in slugs
    # Check member_count is present
    matching = [t for t in data if t["slug"] == slug]
    assert matching[0]["member_count"] == 1


# --- Test: Non-platform-admin cannot access admin endpoints ---


async def test_non_admin_cannot_list_tenants(client: AsyncClient):
    """Regular user gets 403 on admin endpoints."""
    uid = _uid()
    headers = auth_headers(sub=f"regular-{uid}", email=f"regular-{uid}@test.com")

    r = await client.get("/api/v1/admin/tenants", headers=headers)
    assert r.status_code == 403
    assert "Platform admin" in r.json()["detail"]


# --- Test: Platform admin can suspend a tenant ---


async def test_platform_admin_can_suspend_tenant(client: AsyncClient, db: AsyncSession):
    """Suspend sets is_active=false and returns the updated tenant."""
    admin_headers, _ = await _create_platform_admin(client, db)
    _, slug, tenant_id = await _create_tenant(client)

    r = await client.post(
        f"/api/v1/admin/tenants/{tenant_id}/suspend",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_active"] is False
    assert body["slug"] == slug


# --- Test: Suspend writes audit event ---


async def test_suspend_writes_audit_event(client: AsyncClient, db: AsyncSession):
    """Suspending a tenant creates a tenant.suspended audit event."""
    admin_headers, admin_sub = await _create_platform_admin(client, db)
    _, _, tenant_id = await _create_tenant(client)

    r = await client.post(
        f"/api/v1/admin/tenants/{tenant_id}/suspend",
        headers=admin_headers,
    )
    assert r.status_code == 200

    # Set tenant context to read audit events (RLS)
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    result = await db.execute(
        select(AuditEvent).where(
            AuditEvent.entity_id == uuid.UUID(tenant_id),
            AuditEvent.action == "tenant.suspended",
        )
    )
    audit = result.scalar_one_or_none()
    assert audit is not None
    assert audit.entity_type == "tenant"


# --- Test: Platform admin can reactivate a tenant ---


async def test_platform_admin_can_reactivate_tenant(client: AsyncClient, db: AsyncSession):
    """Reactivate sets is_active=true."""
    admin_headers, _ = await _create_platform_admin(client, db)
    _, _, tenant_id = await _create_tenant(client)

    # Suspend first
    r = await client.post(
        f"/api/v1/admin/tenants/{tenant_id}/suspend",
        headers=admin_headers,
    )
    assert r.status_code == 200

    # Reactivate
    r = await client.post(
        f"/api/v1/admin/tenants/{tenant_id}/reactivate",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    # Verify reactivated audit event
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    result = await db.execute(
        select(AuditEvent).where(
            AuditEvent.entity_id == uuid.UUID(tenant_id),
            AuditEvent.action == "tenant.reactivated",
        )
    )
    assert result.scalar_one_or_none() is not None


# --- Test: Suspended tenant gets 403 on tenant-scoped routes ---


async def test_suspended_tenant_gets_403(client: AsyncClient, db: AsyncSession):
    """After suspension, the tenant owner gets 403 on /tenants/me."""
    admin_headers, _ = await _create_platform_admin(client, db)
    owner_headers, _, tenant_id = await _create_tenant(client)

    # Verify owner can access tenant before suspension
    r = await client.get("/api/v1/tenants/me", headers=owner_headers)
    assert r.status_code == 200

    # Suspend
    r = await client.post(
        f"/api/v1/admin/tenants/{tenant_id}/suspend",
        headers=admin_headers,
    )
    assert r.status_code == 200

    # Owner should get 403 on all tenant-scoped routes
    r = await client.get("/api/v1/tenants/me", headers=owner_headers)
    assert r.status_code == 403
    assert "suspended" in r.json()["detail"].lower()


# --- Test: Reactivated tenant regains access ---


async def test_reactivated_tenant_regains_access(client: AsyncClient, db: AsyncSession):
    """After reactivation, the tenant owner can access /tenants/me again."""
    admin_headers, _ = await _create_platform_admin(client, db)
    owner_headers, _, tenant_id = await _create_tenant(client)

    # Suspend
    r = await client.post(
        f"/api/v1/admin/tenants/{tenant_id}/suspend",
        headers=admin_headers,
    )
    assert r.status_code == 200

    # Confirm locked out
    r = await client.get("/api/v1/tenants/me", headers=owner_headers)
    assert r.status_code == 403

    # Reactivate
    r = await client.post(
        f"/api/v1/admin/tenants/{tenant_id}/reactivate",
        headers=admin_headers,
    )
    assert r.status_code == 200

    # Owner regains access
    r = await client.get("/api/v1/tenants/me", headers=owner_headers)
    assert r.status_code == 200


# --- Test: Idempotency guards ---


async def test_suspend_already_suspended_returns_409(client: AsyncClient, db: AsyncSession):
    """Suspending an already-suspended tenant returns 409."""
    admin_headers, _ = await _create_platform_admin(client, db)
    _, _, tenant_id = await _create_tenant(client)

    r = await client.post(
        f"/api/v1/admin/tenants/{tenant_id}/suspend",
        headers=admin_headers,
    )
    assert r.status_code == 200

    r = await client.post(
        f"/api/v1/admin/tenants/{tenant_id}/suspend",
        headers=admin_headers,
    )
    assert r.status_code == 409


async def test_reactivate_already_active_returns_409(client: AsyncClient, db: AsyncSession):
    """Reactivating an already-active tenant returns 409."""
    admin_headers, _ = await _create_platform_admin(client, db)
    _, _, tenant_id = await _create_tenant(client)

    r = await client.post(
        f"/api/v1/admin/tenants/{tenant_id}/reactivate",
        headers=admin_headers,
    )
    assert r.status_code == 409


# --- Test: Non-admin cannot suspend ---


async def test_non_admin_cannot_suspend(client: AsyncClient):
    """Regular user cannot suspend tenants."""
    _, _, tenant_id = await _create_tenant(client)

    uid = _uid()
    headers = auth_headers(sub=f"nonadmin-{uid}", email=f"nonadmin-{uid}@test.com")

    r = await client.post(
        f"/api/v1/admin/tenants/{tenant_id}/suspend",
        headers=headers,
    )
    assert r.status_code == 403
