"""M5b inventory / stock enforcement integration tests."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.inventory


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _setup(
    client: AsyncClient,
    *,
    stock_qty: int = 10,
    track_inventory: bool = True,
) -> tuple[dict, str, str, str]:
    """Create tenant + product + visit. Return (headers, slug, product_id, visit_id)."""
    uid = _uid()
    sub = f"inv-{uid}"
    email = f"inv-{uid}@test.com"
    slug = f"inv-{uid}"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/", json={"name": f"Inv {uid}", "slug": slug}, headers=headers
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"StockItem-{uid}",
            "price_amount": "2.500",
            "is_active": True,
            "track_inventory": track_inventory,
            "stock_qty": stock_qty,
        },
        headers=headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]

    r = await client.post(f"/api/v1/storefront/{slug}/visit", json={"session_id": f"sess-{uid}"})
    assert r.status_code == 201
    visit_id = r.json()["visit_id"]

    return headers, slug, product_id, visit_id


async def _submit_order(
    client: AsyncClient, slug: str, product_id: str, visit_id: str, qty: int = 1
):
    """Submit an order and return the response."""
    return await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Test",
            "customer_phone": "+96500000000",
            "items": [{"catalog_item_id": product_id, "qty": qty}],
            "visit_id": visit_id,
        },
    )


async def test_stock_decrements_on_order(client: AsyncClient):
    """Ordering qty=2 from stock=10 should leave stock=8."""
    headers, slug, product_id, visit_id = await _setup(client, stock_qty=10)

    r = await _submit_order(client, slug, product_id, visit_id, qty=2)
    assert r.status_code == 201

    # Verify stock decremented
    r2 = await client.get("/api/v1/tenants/me/products", headers=headers)
    product = next(p for p in r2.json()["items"] if p["id"] == product_id)
    assert product["stock_qty"] == 8


async def test_zero_stock_returns_409(client: AsyncClient):
    """Ordering when stock=0 should return 409."""
    _headers, slug, product_id, visit_id = await _setup(client, stock_qty=0)

    r = await _submit_order(client, slug, product_id, visit_id, qty=1)
    assert r.status_code == 409
    assert "Insufficient stock" in r.json()["detail"]


async def test_insufficient_stock_returns_409(client: AsyncClient):
    """Ordering qty=5 when stock=3 should return 409."""
    _headers, slug, product_id, visit_id = await _setup(client, stock_qty=3)

    r = await _submit_order(client, slug, product_id, visit_id, qty=5)
    assert r.status_code == 409
    assert "Insufficient stock" in r.json()["detail"]


async def test_track_inventory_false_bypasses_stock(client: AsyncClient):
    """Products with track_inventory=False allow unlimited orders."""
    headers, slug, product_id, visit_id = await _setup(client, stock_qty=0, track_inventory=False)

    r = await _submit_order(client, slug, product_id, visit_id, qty=1)
    assert r.status_code == 201


async def _setup_with_category(
    client: AsyncClient,
    *,
    stock_qty: int = 10,
    track_inventory: bool = True,
) -> tuple[str, str, str]:
    """Create tenant + category + product. Return (slug, product_id, category_id).

    The category lets public-list tests filter precisely, avoiding cross-tenant
    noise when the test DB superuser bypasses RLS.
    """
    uid = _uid()
    headers = auth_headers(sub=f"inv-{uid}", email=f"inv-{uid}@test.com")
    headers["Content-Type"] = "application/json"
    slug = f"inv-{uid}"

    r = await client.post(
        "/api/v1/tenants/", json={"name": f"Inv {uid}", "slug": slug}, headers=headers
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/tenants/me/categories",
        json={"name": f"Cat-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201
    category_id = r.json()["id"]

    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"StockItem-{uid}",
            "price_amount": "2.500",
            "is_active": True,
            "track_inventory": track_inventory,
            "stock_qty": stock_qty,
            "category_id": category_id,
        },
        headers=headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]

    return slug, product_id, category_id


async def test_public_product_list_shows_in_stock(client: AsyncClient):
    """Public product list returns in_stock=True and stock_display when stock > 0."""
    slug, pid, cat_id = await _setup_with_category(client, stock_qty=5)

    r = await client.get(f"/api/v1/storefront/{slug}/products?category_id={cat_id}")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    product = items[0]
    assert product["id"] == pid
    assert product["in_stock"] is True
    assert product["stock_display"] == "5 left"
    assert "stock_qty" not in product  # raw qty not exposed


async def test_public_product_out_of_stock(client: AsyncClient):
    """Public product list returns in_stock=False and 'Out of stock' when stock=0."""
    slug, pid, cat_id = await _setup_with_category(client, stock_qty=0)

    r = await client.get(f"/api/v1/storefront/{slug}/products?category_id={cat_id}")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    product = items[0]
    assert product["id"] == pid
    assert product["in_stock"] is False
    assert product["stock_display"] == "Out of stock"


async def test_stock_decrement_is_atomic_no_oversell(client: AsyncClient):
    """Two sequential orders each requesting stock=1 from stock=1: first succeeds, second 409."""
    _headers, slug, product_id, visit_id = await _setup(client, stock_qty=1)

    r1 = await _submit_order(client, slug, product_id, visit_id, qty=1)
    assert r1.status_code == 201

    # Need a new visit for second order
    r_visit = await client.post(
        f"/api/v1/storefront/{slug}/visit", json={"session_id": f"sess2-{_uid()}"}
    )
    visit_id2 = r_visit.json()["visit_id"]

    r2 = await _submit_order(client, slug, product_id, visit_id2, qty=1)
    assert r2.status_code == 409
