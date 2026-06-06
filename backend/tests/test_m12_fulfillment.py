"""M12.6 backend tests: order fulfillment status chain."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from app.models.order import Order
from tests.conftest import auth_headers


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _setup_storefront_order(client: AsyncClient) -> tuple[dict, str, str]:
    """Create tenant + product + a storefront order. Return (headers, tenant_id, order_id)."""
    uid = _uid()
    headers = auth_headers(sub=f"ful-{uid}", email=f"ful-{uid}@test.com")
    headers["Content-Type"] = "application/json"
    slug = f"ful-{uid}"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"Ful {uid}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    tenant_id = r.json()["id"]

    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"FulProd-{uid}",
            "price_amount": "5.000",
            "is_active": True,
            "stock_qty": 100,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    product_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Buyer",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201, r.text
    return headers, tenant_id, r.json()["id"]


async def _patch_fulfillment(client: AsyncClient, headers: dict, order_id: str, value: str):
    return await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/fulfillment",
        json={"fulfillment_status": value},
        headers=headers,
    )


async def _patch_status(client: AsyncClient, headers: dict, order_id: str, value: str):
    return await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": value},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# 1. Happy path + DB + audit
# ---------------------------------------------------------------------------


async def test_fulfillment_happy_path_and_audit(client: AsyncClient, db: AsyncSession):
    headers, tenant_id, order_id = await _setup_storefront_order(client)

    r = await client.get(f"/api/v1/tenants/me/orders/{order_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["fulfillment_status"] is None

    for value in ["packed", "shipped", "delivered"]:
        r = await _patch_fulfillment(client, headers, order_id, value)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["fulfillment_status"] == value
        assert data["status"] == "pending"  # order status untouched by fulfillment

    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    order = (await db.execute(select(Order).where(Order.id == uuid.UUID(order_id)))).scalar_one()
    assert order.fulfillment_status == "delivered"
    assert order.status == "pending"

    events = list(
        (
            await db.execute(
                select(AuditEvent).where(
                    AuditEvent.entity_id == uuid.UUID(order_id),
                    AuditEvent.action == "fulfillment_transition",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 3
    pairs = {(e.from_status, e.to_status) for e in events}
    assert pairs == {
        ("unfulfilled", "packed"),
        ("packed", "shipped"),
        ("shipped", "delivered"),
    }


# ---------------------------------------------------------------------------
# 2. Invalid transitions (skip / backward / terminal)
# ---------------------------------------------------------------------------


async def test_fulfillment_rejects_skip_from_unfulfilled(client: AsyncClient):
    headers, _tenant_id, order_id = await _setup_storefront_order(client)
    assert (await _patch_fulfillment(client, headers, order_id, "shipped")).status_code == 422
    assert (await _patch_fulfillment(client, headers, order_id, "delivered")).status_code == 422


async def test_fulfillment_rejects_skip_from_packed(client: AsyncClient):
    headers, _tenant_id, order_id = await _setup_storefront_order(client)
    assert (await _patch_fulfillment(client, headers, order_id, "packed")).status_code == 200
    assert (await _patch_fulfillment(client, headers, order_id, "delivered")).status_code == 422


async def test_fulfillment_rejects_backward_from_shipped(client: AsyncClient):
    headers, _tenant_id, order_id = await _setup_storefront_order(client)
    assert (await _patch_fulfillment(client, headers, order_id, "packed")).status_code == 200
    assert (await _patch_fulfillment(client, headers, order_id, "shipped")).status_code == 200
    assert (await _patch_fulfillment(client, headers, order_id, "packed")).status_code == 422


async def test_fulfillment_delivered_is_terminal(client: AsyncClient):
    headers, _tenant_id, order_id = await _setup_storefront_order(client)
    for value in ["packed", "shipped", "delivered"]:
        assert (await _patch_fulfillment(client, headers, order_id, value)).status_code == 200
    assert (await _patch_fulfillment(client, headers, order_id, "shipped")).status_code == 422
    assert (await _patch_fulfillment(client, headers, order_id, "packed")).status_code == 422
    assert (await _patch_fulfillment(client, headers, order_id, "delivered")).status_code == 422


# ---------------------------------------------------------------------------
# 3. Gates
# ---------------------------------------------------------------------------


async def test_fulfillment_blocked_when_cancelled(client: AsyncClient):
    headers, _tenant_id, order_id = await _setup_storefront_order(client)
    assert (await _patch_status(client, headers, order_id, "cancelled")).status_code == 200
    assert (await _patch_fulfillment(client, headers, order_id, "packed")).status_code == 422


async def test_fulfillment_blocked_when_status_fulfilled(client: AsyncClient):
    headers, _tenant_id, order_id = await _setup_storefront_order(client)
    assert (await _patch_status(client, headers, order_id, "confirmed")).status_code == 200
    assert (await _patch_status(client, headers, order_id, "fulfilled")).status_code == 200
    assert (await _patch_fulfillment(client, headers, order_id, "packed")).status_code == 422


async def test_fulfillment_blocked_for_pos_order(client: AsyncClient):
    uid = _uid()
    headers = auth_headers(sub=f"fulpos-{uid}", email=f"fulpos-{uid}@test.com")
    headers["Content-Type"] = "application/json"
    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"FulPos {uid}", "slug": f"fulpos-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201
    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"PosProd-{uid}",
            "price_amount": "5.000",
            "is_active": True,
            "stock_qty": 10,
        },
        headers=headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]
    r = await client.post(
        "/api/v1/tenants/me/pos/shifts/open",
        json={"starting_cash": "0.000"},
        headers=headers,
    )
    assert r.status_code == 201
    r = await client.post(
        "/api/v1/tenants/me/pos/orders",
        json={"items": [{"catalog_item_id": product_id, "qty": 1}]},
        headers=headers,
    )
    assert r.status_code == 201
    pos_order_id = r.json()["id"]
    assert (await _patch_fulfillment(client, headers, pos_order_id, "packed")).status_code == 422


async def test_fulfillment_unknown_order_404(client: AsyncClient):
    headers, _tenant_id, _order_id = await _setup_storefront_order(client)
    r = await _patch_fulfillment(client, headers, str(uuid.uuid4()), "packed")
    assert r.status_code == 404


async def test_fulfillment_cross_tenant_404(client: AsyncClient):
    headers_a, _ta, order_a = await _setup_storefront_order(client)
    headers_b, _tb, _order_b = await _setup_storefront_order(client)
    # Tenant B (admin) cannot fulfill tenant A's order.
    r = await _patch_fulfillment(client, headers_b, order_a, "packed")
    assert r.status_code == 404


async def test_fulfillment_non_admin_403(client: AsyncClient):
    headers, _tenant_id, order_id = await _setup_storefront_order(client)
    uid = _uid()
    member_email = f"fulmem-{uid}@test.com"
    r = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": member_email, "role": "member"},
        headers=headers,
    )
    assert r.status_code == 201
    member_headers = auth_headers(sub=f"fulmem-{uid}", email=member_email)
    member_headers["Content-Type"] = "application/json"
    r = await client.post("/api/v1/auth/accept-invite", headers=member_headers)
    assert r.status_code == 200
    resp = await _patch_fulfillment(client, member_headers, order_id, "packed")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 4. Response exposure
# ---------------------------------------------------------------------------


async def test_order_detail_includes_fulfillment_status(client: AsyncClient):
    headers, _tenant_id, order_id = await _setup_storefront_order(client)
    assert (await _patch_fulfillment(client, headers, order_id, "packed")).status_code == 200
    r = await client.get(f"/api/v1/tenants/me/orders/{order_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["fulfillment_status"] == "packed"


async def test_order_list_includes_fulfillment_status(client: AsyncClient):
    headers, _tenant_id, order_id = await _setup_storefront_order(client)
    assert (await _patch_fulfillment(client, headers, order_id, "packed")).status_code == 200
    r = await client.get("/api/v1/tenants/me/orders", headers=headers)
    assert r.status_code == 200
    match = [o for o in r.json() if o["id"] == order_id]
    assert len(match) == 1
    assert match[0]["fulfillment_status"] == "packed"
