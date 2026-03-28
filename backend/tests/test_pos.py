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
