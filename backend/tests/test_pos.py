"""POS order endpoint integration tests."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.pos


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _setup(
    client: AsyncClient,
    *,
    stock_qty: int = 10,
    track_inventory: bool = True,
) -> tuple[dict, str]:
    # Create tenant + product, return (headers, product_id).
    uid = _uid()
    sub = f"pos-{uid}"
    email = f"pos-{uid}@test.com"
    slug = f"pos-{uid}"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"POS {uid}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"POSItem-{uid}",
            "price_amount": "5.000",
            "is_active": True,
            "track_inventory": track_inventory,
            "stock_qty": stock_qty,
        },
        headers=headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]

    return headers, product_id


async def test_pos_order_happy_path(client: AsyncClient):
    # POS order creates fulfilled order with source=pos and decrements stock.
    headers, product_id = await _setup(client, stock_qty=10)

    r = await client.post(
        "/api/v1/tenants/me/pos/orders",
        json={"items": [{"catalog_item_id": product_id, "qty": 2}]},
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "fulfilled"
    assert data["source"] == "pos"
    assert data["order_number"].startswith("ORD-")

    # Verify stock decremented
    r = await client.get(
        f"/api/v1/tenants/me/products/{product_id}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["stock_qty"] == 8


async def test_pos_order_insufficient_stock(client: AsyncClient):
    # POS order fails with 409 when stock is insufficient.
    headers, product_id = await _setup(client, stock_qty=3)

    r = await client.post(
        "/api/v1/tenants/me/pos/orders",
        json={"items": [{"catalog_item_id": product_id, "qty": 5}]},
        headers=headers,
    )
    assert r.status_code == 409


async def test_pos_order_inactive_product(client: AsyncClient):
    # POS order fails with 422 for inactive product.
    headers, product_id = await _setup(client)

    # Deactivate the product
    r = await client.patch(
        f"/api/v1/tenants/me/products/{product_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert r.status_code == 200

    r = await client.post(
        "/api/v1/tenants/me/pos/orders",
        json={"items": [{"catalog_item_id": product_id, "qty": 1}]},
        headers=headers,
    )
    assert r.status_code == 422


async def test_pos_order_cross_tenant_rejected(client: AsyncClient):
    # POS order rejects product from a different tenant.
    headers_a, product_id_a = await _setup(client)

    uid = _uid()
    headers_b = auth_headers(sub=f"pos-b-{uid}", email=f"pos-b-{uid}@test.com")
    headers_b["Content-Type"] = "application/json"
    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"POS-B {uid}", "slug": f"pos-b-{uid}"},
        headers=headers_b,
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/tenants/me/pos/orders",
        json={"items": [{"catalog_item_id": product_id_a, "qty": 1}]},
        headers=headers_b,
    )
    assert r.status_code == 422


async def test_pos_order_source_persists_in_list(client: AsyncClient):
    # POS order source=pos is visible in the orders list.
    headers, product_id = await _setup(client)

    r = await client.post(
        "/api/v1/tenants/me/pos/orders",
        json={"items": [{"catalog_item_id": product_id, "qty": 1}]},
        headers=headers,
    )
    assert r.status_code == 201

    r = await client.get("/api/v1/tenants/me/orders", headers=headers)
    assert r.status_code == 200
    orders = r.json()
    assert len(orders) == 1
    assert orders[0]["source"] == "pos"


# ---------------------------------------------------------------------------
# Helpers for order-history tests
# ---------------------------------------------------------------------------


async def _setup_with_slug(
    client: AsyncClient,
) -> tuple[dict, str, str]:
    # Create tenant + product, return (owner_headers, product_id, slug).
    uid = _uid()
    slug = f"pos-{uid}"
    headers = auth_headers(sub=f"pos-{uid}", email=f"pos-{uid}@test.com")
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"POS {uid}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"POSItem-{uid}",
            "price_amount": "5.000",
            "is_active": True,
            "track_inventory": True,
            "stock_qty": 50,
        },
        headers=headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]

    return headers, product_id, slug


async def _invite_cashier(
    client: AsyncClient,
    owner_headers: dict,
) -> dict:
    # Invite + accept a cashier; return cashier headers.
    uid = _uid()
    cashier_email = f"cashier-{uid}@test.com"

    r = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": cashier_email, "role": "cashier"},
        headers=owner_headers,
    )
    assert r.status_code == 201

    cashier_headers = auth_headers(
        sub=f"cashier-{uid}", email=cashier_email
    )
    cashier_headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/auth/accept-invite",
        headers=cashier_headers,
    )
    assert r.status_code == 200

    return cashier_headers


# ---------------------------------------------------------------------------
# Order-history tests
# ---------------------------------------------------------------------------


async def test_cashier_can_list_pos_orders(client: AsyncClient):
    # Cashier can list POS orders for their tenant.
    owner_headers, product_id, _ = await _setup_with_slug(client)
    cashier_headers = await _invite_cashier(client, owner_headers)

    r = await client.post(
        "/api/v1/tenants/me/pos/orders",
        json={"items": [{"catalog_item_id": product_id, "qty": 1}]},
        headers=cashier_headers,
    )
    assert r.status_code == 201

    r = await client.get(
        "/api/v1/tenants/me/pos/orders",
        headers=cashier_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["source"] == "pos"
    assert data["has_more"] is False


async def test_pos_list_excludes_storefront_orders(client: AsyncClient):
    # POS order list never includes storefront orders.
    owner_headers, product_id, slug = await _setup_with_slug(client)

    # Create one POS order
    r = await client.post(
        "/api/v1/tenants/me/pos/orders",
        json={"items": [{"catalog_item_id": product_id, "qty": 1}]},
        headers=owner_headers,
    )
    assert r.status_code == 201

    # Create one storefront order via the public endpoint
    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Walk-in",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201

    r = await client.get(
        "/api/v1/tenants/me/pos/orders",
        headers=owner_headers,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["source"] == "pos"


async def test_pos_order_detail_happy_path(client: AsyncClient):
    # GET /pos/orders/{id} returns the correct order detail.
    owner_headers, product_id, _ = await _setup_with_slug(client)

    r = await client.post(
        "/api/v1/tenants/me/pos/orders",
        json={"items": [{"catalog_item_id": product_id, "qty": 2}]},
        headers=owner_headers,
    )
    assert r.status_code == 201
    created = r.json()

    r = await client.get(
        f"/api/v1/tenants/me/pos/orders/{created['id']}",
        headers=owner_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == created["id"]
    assert data["source"] == "pos"
    assert data["order_number"] == created["order_number"]
    assert len(data["items"]) == 1
    assert data["items"][0]["qty"] == 2


async def test_pos_detail_404_for_storefront_order(client: AsyncClient):
    # GET /pos/orders/{id} returns 404 for a real storefront order.
    owner_headers, product_id, slug = await _setup_with_slug(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Walk-in",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201
    sf_id = r.json()["id"]

    r = await client.get(
        f"/api/v1/tenants/me/pos/orders/{sf_id}",
        headers=owner_headers,
    )
    assert r.status_code == 404
