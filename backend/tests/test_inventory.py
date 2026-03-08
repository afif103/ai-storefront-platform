"""M5b/M5c inventory / stock enforcement + movement integration tests."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock_movement import StockMovement
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


# ---------------------------------------------------------------------------
# M5c Packet 1 — cancel restore + stock movement tests
# ---------------------------------------------------------------------------


async def test_cancel_restores_stock_for_tracked_product(client: AsyncClient):
    """Cancelling an order restores stock for tracked-inventory products."""
    headers, slug, product_id, visit_id = await _setup(client, stock_qty=10)

    # Buy qty=3 → stock should be 7
    r = await _submit_order(client, slug, product_id, visit_id, qty=3)
    assert r.status_code == 201
    order_id = r.json()["id"]

    # Cancel the order
    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    # Verify stock restored to 10
    r2 = await client.get("/api/v1/tenants/me/products", headers=headers)
    product = next(p for p in r2.json()["items"] if p["id"] == product_id)
    assert product["stock_qty"] == 10


async def test_cancel_does_not_affect_untracked_product(client: AsyncClient):
    """Cancelling an order with track_inventory=False does not create movements."""
    headers, slug, product_id, visit_id = await _setup(client, stock_qty=0, track_inventory=False)

    r = await _submit_order(client, slug, product_id, visit_id, qty=2)
    assert r.status_code == 201
    order_id = r.json()["id"]

    # Cancel — should succeed but not touch stock
    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert r.status_code == 200

    # Stock should still be 0 (untracked, no restore)
    r2 = await client.get("/api/v1/tenants/me/products", headers=headers)
    product = next(p for p in r2.json()["items"] if p["id"] == product_id)
    assert product["stock_qty"] == 0


async def test_repeated_cancel_does_not_double_restore(client: AsyncClient):
    """Second cancel attempt is rejected by transition rules; stock restored only once."""
    headers, slug, product_id, visit_id = await _setup(client, stock_qty=10)

    r = await _submit_order(client, slug, product_id, visit_id, qty=5)
    assert r.status_code == 201
    order_id = r.json()["id"]

    # First cancel → 200, stock restored
    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert r.status_code == 200

    # Second cancel → 422 (cancelled→cancelled not allowed)
    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert r.status_code == 422

    # Stock should be exactly 10 (not 15)
    r2 = await client.get("/api/v1/tenants/me/products", headers=headers)
    product = next(p for p in r2.json()["items"] if p["id"] == product_id)
    assert product["stock_qty"] == 10


async def test_cancel_writes_stock_movement_rows(client: AsyncClient, db: AsyncSession):
    """Cancelling an order creates correct stock_movements rows."""
    headers, slug, product_id, visit_id = await _setup(client, stock_qty=10)

    r = await _submit_order(client, slug, product_id, visit_id, qty=4)
    assert r.status_code == 201
    order_id = r.json()["id"]

    # Get tenant_id
    r_t = await client.get("/api/v1/tenants/me", headers=headers)
    tenant_id = r_t.json()["id"]

    # Cancel
    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert r.status_code == 200

    # Query stock_movements via DB
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    result = await db.execute(
        select(StockMovement).where(
            StockMovement.order_id == uuid.UUID(order_id),
        )
    )
    movements = list(result.scalars().all())

    assert len(movements) == 1
    m = movements[0]
    assert m.product_id == uuid.UUID(product_id)
    assert m.delta_qty == 4
    assert m.reason == "order_cancel_restore"
    assert m.order_id == uuid.UUID(order_id)
    assert m.actor_user_id is not None  # admin who cancelled
    assert m.note is not None and "cancelled" in m.note.lower()


async def test_mixed_order_tracked_and_untracked_restore(client: AsyncClient, db: AsyncSession):
    """Cancel of a mixed order restores only tracked items, not untracked."""
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
    tenant_id = r.json()["id"]

    # Create tracked product (stock=10)
    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"Tracked-{uid}",
            "price_amount": "3.000",
            "is_active": True,
            "track_inventory": True,
            "stock_qty": 10,
        },
        headers=headers,
    )
    assert r.status_code == 201
    tracked_id = r.json()["id"]

    # Create untracked product
    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"Untracked-{uid}",
            "price_amount": "2.000",
            "is_active": True,
            "track_inventory": False,
            "stock_qty": 0,
        },
        headers=headers,
    )
    assert r.status_code == 201
    untracked_id = r.json()["id"]

    # Create visit
    r = await client.post(f"/api/v1/storefront/{slug}/visit", json={"session_id": f"sess-{uid}"})
    assert r.status_code == 201
    visit_id = r.json()["visit_id"]

    # Submit order with both products
    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "MixTest",
            "items": [
                {"catalog_item_id": tracked_id, "qty": 3},
                {"catalog_item_id": untracked_id, "qty": 2},
            ],
            "visit_id": visit_id,
        },
    )
    assert r.status_code == 201
    order_id = r.json()["id"]

    # Cancel
    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert r.status_code == 200

    # Tracked product should be restored: 10-3+3 = 10
    r2 = await client.get("/api/v1/tenants/me/products", headers=headers)
    products = {p["id"]: p for p in r2.json()["items"]}
    assert products[tracked_id]["stock_qty"] == 10
    # Untracked product stock unchanged
    assert products[untracked_id]["stock_qty"] == 0

    # Only 1 stock_movement row (tracked product only)
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    result = await db.execute(
        select(StockMovement).where(
            StockMovement.order_id == uuid.UUID(order_id),
        )
    )
    movements = list(result.scalars().all())
    assert len(movements) == 1
    assert movements[0].product_id == uuid.UUID(tracked_id)
    assert movements[0].delta_qty == 3


# ---------------------------------------------------------------------------
# M5c Packet 2 — restock + stock movement history tests
# ---------------------------------------------------------------------------


async def test_restock_increases_stock_and_creates_movement(client: AsyncClient, db: AsyncSession):
    """POST /restock adds qty, returns updated product, creates movement row."""
    headers, slug, product_id, _visit_id = await _setup(client, stock_qty=5)

    r = await client.post(
        f"/api/v1/tenants/me/products/{product_id}/restock",
        json={"qty": 10, "note": "Weekly restock"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["stock_qty"] == 15

    # Verify movement row
    r_t = await client.get("/api/v1/tenants/me", headers=headers)
    tenant_id = r_t.json()["id"]
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    result = await db.execute(
        select(StockMovement).where(
            StockMovement.product_id == uuid.UUID(product_id),
            StockMovement.reason == "manual_restock",
        )
    )
    movements = list(result.scalars().all())
    assert len(movements) == 1
    assert movements[0].delta_qty == 10
    assert movements[0].note == "Weekly restock"
    assert movements[0].actor_user_id is not None


async def test_restock_rejects_untracked_product(client: AsyncClient):
    """POST /restock on track_inventory=False returns 422."""
    headers, _slug, product_id, _visit_id = await _setup(
        client, stock_qty=0, track_inventory=False
    )

    r = await client.post(
        f"/api/v1/tenants/me/products/{product_id}/restock",
        json={"qty": 5},
        headers=headers,
    )
    assert r.status_code == 422
    assert "does not track inventory" in r.json()["detail"]


async def test_restock_rejects_zero_and_negative_qty(client: AsyncClient):
    """POST /restock with qty <= 0 returns 422 (Pydantic validation)."""
    headers, _slug, product_id, _visit_id = await _setup(client, stock_qty=5)

    for bad_qty in [0, -3]:
        r = await client.post(
            f"/api/v1/tenants/me/products/{product_id}/restock",
            json={"qty": bad_qty},
            headers=headers,
        )
        assert r.status_code == 422


async def test_stock_movements_history_endpoint(client: AsyncClient):
    """GET /stock-movements returns recent movements newest-first."""
    headers, slug, product_id, visit_id = await _setup(client, stock_qty=10)

    # Create a movement via restock
    r = await client.post(
        f"/api/v1/tenants/me/products/{product_id}/restock",
        json={"qty": 5, "note": "first restock"},
        headers=headers,
    )
    assert r.status_code == 200

    # Create another movement via cancel
    r = await _submit_order(client, slug, product_id, visit_id, qty=2)
    assert r.status_code == 201
    order_id = r.json()["id"]

    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert r.status_code == 200

    # Fetch history
    r = await client.get(
        f"/api/v1/tenants/me/products/{product_id}/stock-movements",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    items = data["items"]

    # Should have 2 movements: cancel restore (newest) + restock
    assert len(items) == 2
    assert items[0]["reason"] == "order_cancel_restore"
    assert items[0]["delta_qty"] == 2
    assert items[0]["order_id"] == order_id
    assert items[1]["reason"] == "manual_restock"
    assert items[1]["delta_qty"] == 5
    assert items[1]["note"] == "first restock"


# ---------------------------------------------------------------------------
# M5c Packet 3 — low-stock threshold + is_low_stock tests
# ---------------------------------------------------------------------------


async def test_is_low_stock_true_when_at_threshold(client: AsyncClient):
    """Product with stock_qty == low_stock_threshold → is_low_stock=True."""
    headers, _slug, product_id, _visit_id = await _setup(client, stock_qty=5)

    # Default threshold is 5, stock=5 → at threshold → low stock
    r = await client.get(f"/api/v1/tenants/me/products/{product_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["is_low_stock"] is True
    assert data["low_stock_threshold"] == 5


async def test_is_low_stock_true_when_below_threshold(client: AsyncClient):
    """Product with stock_qty < low_stock_threshold → is_low_stock=True."""
    headers, _slug, product_id, _visit_id = await _setup(client, stock_qty=3)

    r = await client.get(f"/api/v1/tenants/me/products/{product_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["is_low_stock"] is True


async def test_is_low_stock_false_when_above_threshold(client: AsyncClient):
    """Product with stock_qty > low_stock_threshold → is_low_stock=False."""
    headers, _slug, product_id, _visit_id = await _setup(client, stock_qty=10)

    r = await client.get(f"/api/v1/tenants/me/products/{product_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["is_low_stock"] is False


async def test_is_low_stock_false_when_out_of_stock(client: AsyncClient):
    """Product with stock_qty=0 → is_low_stock=False (out-of-stock is separate state)."""
    headers, _slug, product_id, _visit_id = await _setup(client, stock_qty=0)

    r = await client.get(f"/api/v1/tenants/me/products/{product_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["is_low_stock"] is False


async def test_is_low_stock_false_when_untracked(client: AsyncClient):
    """Untracked products never report is_low_stock=True."""
    headers, _slug, product_id, _visit_id = await _setup(
        client, stock_qty=0, track_inventory=False
    )

    r = await client.get(f"/api/v1/tenants/me/products/{product_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["is_low_stock"] is False


async def test_is_low_stock_false_when_threshold_zero(client: AsyncClient):
    """Product with low_stock_threshold=0 (disabled) → is_low_stock=False."""
    uid = _uid()
    headers = auth_headers(sub=f"inv-{uid}", email=f"inv-{uid}@test.com")
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"Inv {uid}", "slug": f"inv-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"Item-{uid}",
            "price_amount": "1.000",
            "track_inventory": True,
            "stock_qty": 2,
            "low_stock_threshold": 0,
        },
        headers=headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]

    r = await client.get(f"/api/v1/tenants/me/products/{product_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["is_low_stock"] is False


async def test_custom_threshold_respected(client: AsyncClient):
    """Product with custom low_stock_threshold=20 and stock=15 → is_low_stock=True."""
    uid = _uid()
    headers = auth_headers(sub=f"inv-{uid}", email=f"inv-{uid}@test.com")
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"Inv {uid}", "slug": f"inv-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"Item-{uid}",
            "price_amount": "1.000",
            "track_inventory": True,
            "stock_qty": 15,
            "low_stock_threshold": 20,
        },
        headers=headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]

    r = await client.get(f"/api/v1/tenants/me/products/{product_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["is_low_stock"] is True
    assert r.json()["low_stock_threshold"] == 20
