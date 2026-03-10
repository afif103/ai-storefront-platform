"""M6 P2 — Role change + CSV export integration tests."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from app.models.tenant_member import TenantMember
from app.models.user import User
from tests.conftest import auth_headers

pytestmark = pytest.mark.m6


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _setup_tenant_with_two_members(
    client: AsyncClient, db: AsyncSession
) -> tuple[dict, dict, str, str, str, str]:
    """Create tenant with owner + a second active member via DB.

    Returns (owner_headers, member_headers, slug, tenant_id,
             owner_membership_id, member_membership_id).
    """
    uid = _uid()

    # Owner — creates tenant via API (auto-provisions user + membership)
    owner_sub = f"owner-{uid}"
    owner_email = f"owner-{uid}@test.com"
    owner_headers = auth_headers(sub=owner_sub, email=owner_email)
    owner_headers["Content-Type"] = "application/json"
    slug = f"rp-{uid}"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"RoleTenant {uid}", "slug": slug},
        headers=owner_headers,
    )
    assert r.status_code == 201
    tenant_id = r.json()["id"]

    # Look up owner's membership ID
    owner_user_result = await db.execute(
        select(User).where(User.cognito_sub == owner_sub)
    )
    owner_user = owner_user_result.scalar_one()
    owner_mem_result = await db.execute(
        select(TenantMember).where(
            TenantMember.tenant_id == uuid.UUID(tenant_id),
            TenantMember.user_id == owner_user.id,
            TenantMember.status == "active",
        )
    )
    owner_membership = owner_mem_result.scalar_one()

    # Second user — auto-provision by creating a throwaway tenant
    member_sub = f"mem-{uid}"
    member_email = f"mem-{uid}@test.com"
    member_headers = auth_headers(sub=member_sub, email=member_email)
    member_headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"MemOrg {uid}", "slug": f"mo-{uid}"},
        headers=member_headers,
    )
    assert r.status_code == 201

    # Look up member's user_id
    result = await db.execute(select(User).where(User.cognito_sub == member_sub))
    member_user = result.scalar_one()

    # Directly insert an active membership in the owner's tenant
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    member_row = TenantMember(
        tenant_id=uuid.UUID(tenant_id),
        user_id=member_user.id,
        role="member",
        status="active",
        joined_at=datetime.now(UTC),
    )
    db.add(member_row)
    await db.commit()

    return (
        owner_headers, member_headers, slug, tenant_id,
        str(owner_membership.id), str(member_row.id),
    )


# ---- Role change tests ----


async def test_owner_can_change_member_to_admin(client: AsyncClient, db: AsyncSession):
    """Owner promotes member → admin."""
    owner_h, _, _, _, _, member_id = await _setup_tenant_with_two_members(client, db)

    r = await client.patch(
        f"/api/v1/tenants/me/members/{member_id}",
        json={"role": "admin"},
        headers=owner_h,
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


async def test_owner_can_demote_admin_to_member(client: AsyncClient, db: AsyncSession):
    """Owner demotes admin → member."""
    owner_h, _, _, _, _, member_id = await _setup_tenant_with_two_members(client, db)

    # Promote first
    r = await client.patch(
        f"/api/v1/tenants/me/members/{member_id}",
        json={"role": "admin"},
        headers=owner_h,
    )
    assert r.status_code == 200

    # Demote
    r = await client.patch(
        f"/api/v1/tenants/me/members/{member_id}",
        json={"role": "member"},
        headers=owner_h,
    )
    assert r.status_code == 200
    assert r.json()["role"] == "member"


async def test_non_owner_cannot_change_role(client: AsyncClient, db: AsyncSession):
    """Member (non-owner) gets 403 trying to change roles."""
    _, member_h, _, tenant_id, _, member_id = await _setup_tenant_with_two_members(client, db)

    # Member must target the owner's tenant (they also own their own throwaway tenant)
    member_h["X-Tenant-Id"] = tenant_id
    r = await client.patch(
        f"/api/v1/tenants/me/members/{member_id}",
        json={"role": "admin"},
        headers=member_h,
    )
    assert r.status_code == 403


async def test_cannot_demote_last_owner(client: AsyncClient, db: AsyncSession):
    """Demoting the sole owner returns 400 (self-role-change guard)."""
    owner_h, _, _, _, owner_mid, _ = await _setup_tenant_with_two_members(client, db)

    r = await client.patch(
        f"/api/v1/tenants/me/members/{owner_mid}",
        json={"role": "admin"},
        headers=owner_h,
    )
    # Cannot change own role
    assert r.status_code == 400
    assert "own role" in r.json()["detail"].lower()


async def test_cannot_change_own_role(client: AsyncClient, db: AsyncSession):
    """Owner cannot change their own role (self-demotion guard)."""
    owner_h, _, _, _, owner_mid, _ = await _setup_tenant_with_two_members(client, db)

    r = await client.patch(
        f"/api/v1/tenants/me/members/{owner_mid}",
        json={"role": "member"},
        headers=owner_h,
    )
    assert r.status_code == 400


async def test_role_change_writes_audit_event(client: AsyncClient, db: AsyncSession):
    """Role change creates an audit event."""
    owner_h, _, _, tenant_id, _, member_id = await _setup_tenant_with_two_members(client, db)

    r = await client.patch(
        f"/api/v1/tenants/me/members/{member_id}",
        json={"role": "admin"},
        headers=owner_h,
    )
    assert r.status_code == 200

    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    result = await db.execute(
        select(AuditEvent).where(
            AuditEvent.entity_id == uuid.UUID(member_id),
            AuditEvent.action == "role_change",
        )
    )
    audit = result.scalar_one_or_none()
    assert audit is not None
    assert audit.from_status == "member"
    assert audit.to_status == "admin"


async def test_same_role_returns_409(client: AsyncClient, db: AsyncSession):
    """Changing to the same role returns 409."""
    owner_h, _, _, _, _, member_id = await _setup_tenant_with_two_members(client, db)

    r = await client.patch(
        f"/api/v1/tenants/me/members/{member_id}",
        json={"role": "member"},
        headers=owner_h,
    )
    assert r.status_code == 409


# ---- CSV export tests ----


async def _setup_with_data(client: AsyncClient) -> tuple[dict, str]:
    """Create tenant + order + donation + pledge. Return (headers, slug)."""
    uid = _uid()
    sub = f"exp-{uid}"
    email = f"exp-{uid}@test.com"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"
    slug = f"ex-{uid}"

    r = await client.post(
        "/api/v1/tenants/", json={"name": f"Export {uid}", "slug": slug}, headers=headers
    )
    assert r.status_code == 201

    # Create a product for order
    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"Prod-{uid}",
            "price_amount": "5.000",
            "is_active": True,
            "track_inventory": False,
        },
        headers=headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]

    # Visit for linking
    r = await client.post(
        f"/api/v1/storefront/{slug}/visit", json={"session_id": f"sess-{uid}"}
    )
    assert r.status_code == 201
    visit_id = r.json()["visit_id"]

    # Order
    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "CSV Test",
            "customer_phone": "+96500000001",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
            "visit_id": visit_id,
        },
    )
    assert r.status_code == 201

    # Donation
    r = await client.post(
        f"/api/v1/storefront/{slug}/donations",
        json={
            "donor_name": "CSV Donor",
            "amount": "10.000",
            "visit_id": visit_id,
        },
    )
    assert r.status_code == 201

    # Pledge
    r = await client.post(
        f"/api/v1/storefront/{slug}/pledges",
        json={
            "pledgor_name": "CSV Pledgor",
            "amount": "25.000",
            "target_date": "2026-12-31",
            "visit_id": visit_id,
        },
    )
    assert r.status_code == 201

    return headers, slug


async def test_orders_export_csv(client: AsyncClient):
    """Orders export returns valid CSV with correct headers and data."""
    headers, _ = await _setup_with_data(client)

    r = await client.get("/api/v1/tenants/me/orders/export", headers=headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "orders.csv" in r.headers["content-disposition"]

    # Decode (skip BOM)
    text = r.content.decode("utf-8-sig")
    lines = text.strip().split("\n")
    assert len(lines) >= 2  # header + at least 1 row
    assert "order_number" in lines[0]
    assert "CSV Test" in lines[1]


async def test_donations_export_csv(client: AsyncClient):
    """Donations export returns valid CSV."""
    headers, _ = await _setup_with_data(client)

    r = await client.get("/api/v1/tenants/me/donations/export", headers=headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]

    text = r.content.decode("utf-8-sig")
    lines = text.strip().split("\n")
    assert len(lines) >= 2
    assert "donation_number" in lines[0]
    assert "CSV Donor" in lines[1]


async def test_pledges_export_csv(client: AsyncClient):
    """Pledges export returns valid CSV."""
    headers, _ = await _setup_with_data(client)

    r = await client.get("/api/v1/tenants/me/pledges/export", headers=headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]

    text = r.content.decode("utf-8-sig")
    lines = text.strip().split("\n")
    assert len(lines) >= 2
    assert "pledge_number" in lines[0]
    assert "CSV Pledgor" in lines[1]


async def test_export_empty_returns_headers_only(client: AsyncClient):
    """Export with no data returns CSV with headers only."""
    uid = _uid()
    headers = auth_headers(sub=f"empty-{uid}", email=f"empty-{uid}@test.com")
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"Empty {uid}", "slug": f"em-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201

    r = await client.get("/api/v1/tenants/me/orders/export", headers=headers)
    assert r.status_code == 200
    text = r.content.decode("utf-8-sig")
    lines = text.strip().split("\n")
    assert len(lines) == 1  # headers only
    assert "order_number" in lines[0]


async def test_export_rls_isolation(client: AsyncClient):
    """Tenant A's export does not contain Tenant B's data."""
    # Tenant A with data
    headers_a, _ = await _setup_with_data(client)

    # Tenant B (different user, no data)
    uid = _uid()
    headers_b = auth_headers(sub=f"iso-{uid}", email=f"iso-{uid}@test.com")
    headers_b["Content-Type"] = "application/json"
    await client.post(
        "/api/v1/tenants/",
        json={"name": f"Iso {uid}", "slug": f"iso-{uid}"},
        headers=headers_b,
    )

    # Tenant B's export should be empty (headers only)
    r = await client.get("/api/v1/tenants/me/orders/export", headers=headers_b)
    assert r.status_code == 200
    text = r.content.decode("utf-8-sig")
    lines = text.strip().split("\n")
    assert len(lines) == 1  # headers only, no Tenant A data


async def test_member_cannot_export(client: AsyncClient, db: AsyncSession):
    """Member role (not admin) gets 403 on export."""
    _, member_h, _, tenant_id, _, _ = await _setup_tenant_with_two_members(client, db)

    # Member must target the owner's tenant
    member_h["X-Tenant-Id"] = tenant_id
    r = await client.get("/api/v1/tenants/me/orders/export", headers=member_h)
    assert r.status_code == 403
