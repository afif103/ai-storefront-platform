"""M6 P1 — RLS production-safety test for platform admin endpoints.

Runs admin endpoints through rls_client (app_user DB role, RLS enforced)
to verify behavior matches production where the app connects as app_user.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.conftest import auth_headers

pytestmark = pytest.mark.m6


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _create_platform_admin_rls(
    rls_client: AsyncClient, db: AsyncSession
) -> tuple[dict, str]:
    """Create platform admin user via superuser db, test via rls_client."""
    uid = _uid()
    sub = f"rpadmin-{uid}"
    email = f"rpadmin-{uid}@test.com"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    # Create tenant to auto-provision user (via rls_client = app_user connection)
    r = await rls_client.post(
        "/api/v1/tenants/",
        json={"name": f"RlsAdminOrg {uid}", "slug": f"rao-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201

    # Flag as platform admin via superuser db session
    result = await db.execute(select(User).where(User.cognito_sub == sub))
    user = result.scalar_one()
    user.is_platform_admin = True
    await db.commit()

    return headers, sub


async def _create_tenant_rls(rls_client: AsyncClient) -> tuple[dict, str, str]:
    """Create a tenant via rls_client."""
    uid = _uid()
    sub = f"rowner-{uid}"
    email = f"rowner-{uid}@test.com"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"
    slug = f"rt-{uid}"

    r = await rls_client.post(
        "/api/v1/tenants/",
        json={"name": f"RlsTenant {uid}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201
    return headers, slug, r.json()["id"]


async def test_rls_admin_list_tenants(rls_client: AsyncClient, db: AsyncSession):
    """Platform admin list tenants under app_user RLS."""
    admin_headers, _ = await _create_platform_admin_rls(rls_client, db)
    _, slug, _ = await _create_tenant_rls(rls_client)

    r = await rls_client.get("/api/v1/admin/tenants", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    slugs = [t["slug"] for t in data]
    assert slug in slugs
    # Verify member_count is correct even under RLS
    matching = [t for t in data if t["slug"] == slug]
    actual_count = matching[0]["member_count"]
    print(f"RLS member_count for {slug}: {actual_count}")
    assert (
        actual_count == 1
    ), f"Expected member_count=1, got {actual_count} (RLS may block subquery)"


async def test_rls_admin_list_usage_summary(rls_client: AsyncClient, db: AsyncSession):
    """Usage counts (order/donation/pledge) are correct under app_user RLS."""
    admin_headers, _ = await _create_platform_admin_rls(rls_client, db)
    owner_headers, slug, tenant_id = await _create_tenant_rls(rls_client)

    # Create product (track_inventory=false)
    r = await rls_client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": "RlsProd",
            "price_amount": "5.000",
            "is_active": True,
            "track_inventory": False,
        },
        headers=owner_headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]

    # Visit
    r = await rls_client.post(f"/api/v1/storefront/{slug}/visit", json={"session_id": "rls-sess"})
    assert r.status_code == 201
    visit_id = r.json()["visit_id"]

    # Order
    r = await rls_client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "RlsBuyer",
            "customer_phone": "+96500000002",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
            "visit_id": visit_id,
        },
    )
    assert r.status_code == 201

    # Donation
    r = await rls_client.post(
        f"/api/v1/storefront/{slug}/donations",
        json={"donor_name": "RlsDonor", "amount": "10.000", "visit_id": visit_id},
    )
    assert r.status_code == 201

    # Admin list tenants — verify counts under RLS
    r = await rls_client.get("/api/v1/admin/tenants", headers=admin_headers)
    assert r.status_code == 200
    matching = [t for t in r.json() if t["slug"] == slug]
    assert len(matching) == 1
    td = matching[0]

    assert td["order_count"] == 1, f"RLS order_count: expected 1, got {td['order_count']}"
    assert td["donation_count"] == 1, f"RLS donation_count: expected 1, got {td['donation_count']}"
    assert td["pledge_count"] == 0
    assert td["last_activity_at"] is not None


async def test_rls_admin_suspend_and_audit(rls_client: AsyncClient, db: AsyncSession):
    """Suspend + audit event write works under app_user RLS."""
    admin_headers, _ = await _create_platform_admin_rls(rls_client, db)
    _, _, tenant_id = await _create_tenant_rls(rls_client)

    r = await rls_client.post(
        f"/api/v1/admin/tenants/{tenant_id}/suspend",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


async def test_rls_suspended_tenant_403(rls_client: AsyncClient, db: AsyncSession):
    """Suspended tenant gets 403 under app_user RLS."""
    admin_headers, _ = await _create_platform_admin_rls(rls_client, db)
    owner_headers, _, tenant_id = await _create_tenant_rls(rls_client)

    # Suspend
    r = await rls_client.post(
        f"/api/v1/admin/tenants/{tenant_id}/suspend",
        headers=admin_headers,
    )
    assert r.status_code == 200

    # Owner should get 403
    r = await rls_client.get("/api/v1/tenants/me", headers=owner_headers)
    assert r.status_code == 403
