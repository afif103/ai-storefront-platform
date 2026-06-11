"""M13.3 backend tests: POS-only single-day analytics snapshot.

Read-only `GET /tenants/me/analytics/pos-today?date=YYYY-MM-DD`. Covers
non-cancelled POS orders (source='pos') within the local day window
[date, date + 1 day):
  * pos_sales / pos_order_count -> SUM(total_amount) / COUNT(*)
  * by_payment_method           -> grouped, NULL bucket preserved
  * top_products                -> line-subtotal aggregation over items JSONB, LIMIT 5
Storefront orders, cancelled orders, and other-day orders are excluded. Every
test uses its own fresh tenant, so assertions are scoped to records created
within the test and unaffected by the persistent dev DB / cross-test accumulation.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _line(product_id: str, qty: int = 1) -> dict:
    return {"catalog_item_id": product_id, "qty": qty}


def _today_qs() -> str:
    """The frontend sends its local 'today' as date=YYYY-MM-DD."""
    return f"date={date.today()}"


async def _create_product(client: AsyncClient, headers: dict, name: str, price: str) -> str:
    r = await client.post(
        "/api/v1/tenants/me/products",
        json={"name": name, "price_amount": price, "is_active": True, "stock_qty": 1000},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _setup(client: AsyncClient) -> tuple[dict, str, str]:
    """Create tenant + a 5.000-priced active product. Return (headers, slug, product_id)."""
    uid = _uid()
    headers = auth_headers(sub=f"pos-{uid}", email=f"pos-{uid}@test.com")
    headers["Content-Type"] = "application/json"
    slug = f"pos-{uid}"
    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"POS {uid}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    pid = await _create_product(client, headers, f"PosProd-{uid}", "5.000")
    return headers, slug, pid


async def _submit_storefront_order(client: AsyncClient, slug: str, *, items: list[dict]) -> dict:
    body: dict = {
        "customer_name": "Buyer",
        "customer_email": f"buyer-{_uid()}@e.com",
        "items": items,
    }
    r = await client.post(f"/api/v1/storefront/{slug}/orders", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def _open_shift(client: AsyncClient, headers: dict) -> None:
    r = await client.post(
        "/api/v1/tenants/me/pos/shifts/open",
        json={"starting_cash": "0.000"},
        headers=headers,
    )
    assert r.status_code == 201, r.text


async def _create_pos_order(
    client: AsyncClient,
    headers: dict,
    *,
    items: list[dict],
    payment_method: str | None = None,
) -> dict:
    body: dict = {"items": items}
    if payment_method is not None:
        body["payment_method"] = payment_method
    r = await client.post("/api/v1/tenants/me/pos/orders", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _cancel_pos_order(client: AsyncClient, headers: dict, order_id: str) -> dict:
    r = await client.patch(f"/api/v1/tenants/me/pos/orders/{order_id}/cancel", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _invite(client: AsyncClient, owner_headers: dict, role: str) -> dict:
    uid = _uid()
    email = f"posm-{uid}@test.com"
    r = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": email, "role": role},
        headers=owner_headers,
    )
    assert r.status_code == 201, r.text
    member_headers = auth_headers(sub=f"posm-{uid}", email=email)
    member_headers["Content-Type"] = "application/json"
    r = await client.post("/api/v1/auth/accept-invite", headers=member_headers)
    assert r.status_code == 200, r.text
    return member_headers


async def _backdate_order(db: AsyncSession, order_id: str, new_created_at: datetime) -> None:
    """Test-only setup: move an order's created_at to a fixed past timestamp (committed)."""
    await db.execute(
        text("UPDATE orders SET created_at = :ts WHERE id = :oid"),
        {"ts": new_created_at, "oid": uuid.UUID(order_id)},
    )
    await db.commit()


async def _get_pos_today(client: AsyncClient, headers: dict, qs: str | None = None):
    qs = qs if qs is not None else _today_qs()
    return await client.get(f"/api/v1/tenants/me/analytics/pos-today?{qs}", headers=headers)


# ---------------------------------------------------------------------------
# Empty / shape
# ---------------------------------------------------------------------------


async def test_empty_returns_zeros_and_kwd(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    r = await _get_pos_today(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["currency"] == "KWD"
    assert data["date"] == str(date.today())
    assert data["pos_sales"] == "0.000"
    assert data["pos_order_count"] == 0
    assert data["by_payment_method"] == []
    assert data["top_products"] == []


# ---------------------------------------------------------------------------
# Single POS order today
# ---------------------------------------------------------------------------


async def test_single_pos_order_today(client: AsyncClient):
    headers, _slug, pid = await _setup(client)
    await _open_shift(client, headers)
    order = await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")

    r = await _get_pos_today(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["currency"] == order["currency"]
    assert data["pos_sales"] == "5.000"
    assert data["pos_order_count"] == 1
    methods = data["by_payment_method"]
    assert len(methods) == 1
    assert methods[0] == {"payment_method": "cash", "order_count": 1, "gross_sales": "5.000"}
    assert len(data["top_products"]) == 1
    prod = data["top_products"][0]
    assert prod["product_id"] == pid
    assert prod["qty_sold"] == 1
    assert prod["gross_sales"] == "5.000"


# ---------------------------------------------------------------------------
# Exclusions: storefront, cancelled, other-day
# ---------------------------------------------------------------------------


async def test_storefront_order_excluded(client: AsyncClient):
    headers, slug, pid_pos = await _setup(client)
    # A storefront order on a different product must NOT appear in the POS snapshot.
    pid_store = await _create_product(client, headers, f"StoreProd-{_uid()}", "9.000")
    await _submit_storefront_order(client, slug, items=[_line(pid_store, 1)])
    await _open_shift(client, headers)
    await _create_pos_order(client, headers, items=[_line(pid_pos, 1)], payment_method="cash")

    r = await _get_pos_today(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pos_sales"] == "5.000"  # POS only, not 14.000
    assert data["pos_order_count"] == 1
    product_ids = {p["product_id"] for p in data["top_products"]}
    assert product_ids == {pid_pos}
    assert pid_store not in product_ids


async def test_cancelled_pos_order_excluded(client: AsyncClient):
    headers, _slug, pid = await _setup(client)
    await _open_shift(client, headers)
    pos = await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")
    await _cancel_pos_order(client, headers, pos["id"])
    # A non-cancelled POS order with a different method remains.
    await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="knet")

    r = await _get_pos_today(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pos_sales"] == "5.000"  # only the knet order
    assert data["pos_order_count"] == 1
    # the cancelled order's 'cash' bucket must not leak in
    methods = data["by_payment_method"]
    assert len(methods) == 1
    assert methods[0] == {"payment_method": "knet", "order_count": 1, "gross_sales": "5.000"}
    assert len(data["top_products"]) == 1
    assert data["top_products"][0]["qty_sold"] == 1
    assert data["top_products"][0]["gross_sales"] == "5.000"


async def test_only_cancelled_pos_order_returns_zeros_and_kwd(client: AsyncClient):
    headers, _slug, pid = await _setup(client)
    await _open_shift(client, headers)
    pos = await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")
    await _cancel_pos_order(client, headers, pos["id"])

    r = await _get_pos_today(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    # cancelled-only day -> everything zero/empty and currency falls back to KWD
    # (the cancelled row must not supply the currency)
    assert data["currency"] == "KWD"
    assert data["pos_sales"] == "0.000"
    assert data["pos_order_count"] == 0
    assert data["by_payment_method"] == []
    assert data["top_products"] == []


async def test_different_day_pos_order_excluded(client: AsyncClient, db: AsyncSession):
    headers, _slug, pid = await _setup(client)
    await _open_shift(client, headers)
    old = await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")
    # Move it two full days back -> outside today's [date, date + 1) window.
    await _backdate_order(db, old["id"], datetime.now(UTC) - timedelta(days=2))
    # A fresh POS order created today remains in-window.
    await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="knet")

    r = await _get_pos_today(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pos_sales"] == "5.000"  # only today's knet order
    assert data["pos_order_count"] == 1
    methods = data["by_payment_method"]
    assert len(methods) == 1
    assert methods[0] == {"payment_method": "knet", "order_count": 1, "gross_sales": "5.000"}


# ---------------------------------------------------------------------------
# Top products: ordering + LIMIT 5
# ---------------------------------------------------------------------------


async def test_top_products_ordered_desc_and_limited_to_5(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    await _open_shift(client, headers)
    # 6 products priced 1.000 .. 6.000; one POS order (qty 1) each.
    created: list[tuple[int, str]] = []
    for i in range(1, 7):
        pid = await _create_product(client, headers, f"P{i}-{_uid()}", f"{i}.000")
        await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")
        created.append((i, pid))

    r = await _get_pos_today(client, headers)
    assert r.status_code == 200, r.text
    top = r.json()["top_products"]
    assert len(top) == 5
    # gross_sales strictly descending: 6.000 down to 2.000
    assert [p["gross_sales"] for p in top] == [f"{i}.000" for i in range(6, 1, -1)]
    # the cheapest product (1.000) is dropped by LIMIT 5
    returned_ids = {p["product_id"] for p in top}
    assert created[0][1] not in returned_ids


# ---------------------------------------------------------------------------
# Payment-method breakdown
# ---------------------------------------------------------------------------


async def test_payment_breakdown_cash_vs_card(client: AsyncClient):
    headers, _slug, pid = await _setup(client)
    await _open_shift(client, headers)
    # 'knet' is the catalog's card network (no literal 'card' code exists).
    await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")
    await _create_pos_order(client, headers, items=[_line(pid, 2)], payment_method="knet")

    r = await _get_pos_today(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pos_sales"] == "15.000"  # 5.000 + 10.000
    assert data["pos_order_count"] == 2
    # ORDER BY payment_method NULLS LAST -> 'cash' before 'knet'
    assert data["by_payment_method"] == [
        {"payment_method": "cash", "order_count": 1, "gross_sales": "5.000"},
        {"payment_method": "knet", "order_count": 1, "gross_sales": "10.000"},
    ]


async def test_payment_method_null_bucket_preserved(client: AsyncClient):
    headers, _slug, pid = await _setup(client)
    await _open_shift(client, headers)
    # Omit payment_method -> stored NULL.
    await _create_pos_order(client, headers, items=[_line(pid, 1)])

    r = await _get_pos_today(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pos_order_count"] == 1
    methods = data["by_payment_method"]
    assert len(methods) == 1
    bucket = methods[0]
    assert bucket["payment_method"] is None
    assert bucket["order_count"] == 1
    assert bucket["gross_sales"] == "5.000"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def test_missing_date_returns_422(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    r = await client.get("/api/v1/tenants/me/analytics/pos-today", headers=headers)
    assert r.status_code == 422


async def test_malformed_date_returns_422(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    r = await _get_pos_today(client, headers, qs="date=not-a-date")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Auth / role
# ---------------------------------------------------------------------------


async def test_member_role_allowed(client: AsyncClient):
    headers, _slug, pid = await _setup(client)
    await _open_shift(client, headers)
    await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")
    member_headers = await _invite(client, headers, "member")

    r = await _get_pos_today(client, member_headers)
    assert r.status_code == 200, r.text
    assert r.json()["pos_order_count"] == 1


async def test_cashier_role_forbidden(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    cashier_headers = await _invite(client, headers, "cashier")

    r = await _get_pos_today(client, cashier_headers)
    assert r.status_code == 403


async def test_unauthenticated_returns_401(client: AsyncClient):
    r = await client.get(f"/api/v1/tenants/me/analytics/pos-today?{_today_qs()}")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


async def test_cross_tenant_isolation(client: AsyncClient):
    headers_a, _slug_a, pid_a = await _setup(client)
    await _open_shift(client, headers_a)
    await _create_pos_order(client, headers_a, items=[_line(pid_a, 1)], payment_method="cash")

    headers_b, _slug_b, _pid_b = await _setup(client)  # tenant B: no POS orders

    r = await _get_pos_today(client, headers_b)
    assert r.status_code == 200, r.text
    data_b = r.json()
    assert data_b["pos_sales"] == "0.000"
    assert data_b["pos_order_count"] == 0
    assert data_b["by_payment_method"] == []
    assert data_b["top_products"] == []

    r = await _get_pos_today(client, headers_a)
    assert r.json()["pos_order_count"] == 1


# ---------------------------------------------------------------------------
# Regression: M13.1 /analytics/sales, M13.2 /analytics/revenue, funnel /summary
# ---------------------------------------------------------------------------


async def test_existing_analytics_endpoints_still_respond(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)])  # 5.000 storefront
    await _open_shift(client, headers)
    await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")  # 5.000

    today = date.today()
    qs = f"from={today - timedelta(days=7)}&to={today + timedelta(days=1)}"

    r = await client.get(f"/api/v1/tenants/me/analytics/sales?{qs}", headers=headers)
    assert r.status_code == 200, r.text
    sales = r.json()
    for field in ("currency", "total_sales", "total_orders", "by_channel", "by_payment_method"):
        assert field in sales
    assert sales["total_orders"] == 2
    assert sales["total_sales"] == "10.000"

    r = await client.get(f"/api/v1/tenants/me/analytics/revenue?{qs}", headers=headers)
    assert r.status_code == 200, r.text
    revenue = r.json()
    for field in ("currency", "by_day", "top_products"):
        assert field in revenue
    assert len(revenue["by_day"]) == 1
    assert revenue["by_day"][0]["gross_sales"] == "10.000"

    r = await client.get(f"/api/v1/tenants/me/analytics/summary?{qs}", headers=headers)
    assert r.status_code == 200, r.text
    summary = r.json()
    for field in ("visitors", "sessions", "event_counts", "funnel"):
        assert field in summary
