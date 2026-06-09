"""M13.2 backend tests: revenue analytics by day (channel-split) and top products.

Read-only `GET /tenants/me/analytics/revenue`. Two revenue definitions are
deliberately distinct and both are asserted here:
  * by_day uses order.total_amount  -> INCLUDES shipping
  * top_products uses line subtotal -> EXCLUDES shipping
Both cover non-cancelled orders only. Every test uses its own fresh tenant, so
assertions are scoped to records created within the test and are unaffected by
the persistent dev DB / cross-test accumulation.
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


def _valid_range_qs() -> str:
    """A wide, valid range that includes 'now' orders (mirrors the analytics tests)."""
    today = date.today()
    return f"from={today - timedelta(days=7)}&to={today + timedelta(days=1)}"


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
    headers = auth_headers(sub=f"rev-{uid}", email=f"rev-{uid}@test.com")
    headers["Content-Type"] = "application/json"
    slug = f"rev-{uid}"
    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"REV {uid}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    pid = await _create_product(client, headers, f"RevProd-{uid}", "5.000")
    return headers, slug, pid


async def _set_shipping(client: AsyncClient, headers: dict, mid: str, name: str, fee: str) -> None:
    r = await client.put(
        "/api/v1/tenants/me/storefront",
        json={"shipping": {"methods": [{"id": mid, "name": name, "fee": fee, "active": True}]}},
        headers=headers,
    )
    assert r.status_code == 200, r.text


async def _submit_storefront_order(
    client: AsyncClient,
    slug: str,
    *,
    items: list[dict],
    shipping_method_id: str | None = None,
) -> dict:
    body: dict = {
        "customer_name": "Buyer",
        "customer_email": f"buyer-{_uid()}@e.com",
        "items": items,
    }
    if shipping_method_id is not None:
        body["shipping_method_id"] = shipping_method_id
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
    email = f"revm-{uid}@test.com"
    r = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": email, "role": role},
        headers=owner_headers,
    )
    assert r.status_code == 201, r.text
    member_headers = auth_headers(sub=f"revm-{uid}", email=email)
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


async def _get_revenue(client: AsyncClient, headers: dict, qs: str | None = None):
    qs = qs if qs is not None else _valid_range_qs()
    return await client.get(f"/api/v1/tenants/me/analytics/revenue?{qs}", headers=headers)


# ---------------------------------------------------------------------------
# Empty / shape
# ---------------------------------------------------------------------------


async def test_empty_report_returns_no_rows(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    r = await _get_revenue(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["currency"] == "KWD"
    assert data["by_day"] == []
    assert data["top_products"] == []


# ---------------------------------------------------------------------------
# Channel contributions
# ---------------------------------------------------------------------------


async def test_single_storefront_order(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    order = await _submit_storefront_order(client, slug, items=[_line(pid, 1)])

    r = await _get_revenue(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["currency"] == order["currency"]
    assert len(data["by_day"]) == 1
    day = data["by_day"][0]
    assert day["order_count"] == 1
    assert day["gross_sales"] == "5.000"
    assert day["storefront_sales"] == "5.000"
    assert day["pos_sales"] == "0.000"
    assert len(data["top_products"]) == 1
    prod = data["top_products"][0]
    assert prod["product_id"] == pid
    assert prod["qty_sold"] == 1
    assert prod["gross_sales"] == "5.000"


async def test_single_pos_order(client: AsyncClient):
    headers, _slug, pid = await _setup(client)
    await _open_shift(client, headers)
    await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")

    r = await _get_revenue(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["by_day"]) == 1
    day = data["by_day"][0]
    assert day["order_count"] == 1
    assert day["gross_sales"] == "5.000"
    assert day["storefront_sales"] == "0.000"
    assert day["pos_sales"] == "5.000"
    assert len(data["top_products"]) == 1
    assert data["top_products"][0]["product_id"] == pid
    assert data["top_products"][0]["qty_sold"] == 1
    assert data["top_products"][0]["gross_sales"] == "5.000"


async def test_mixed_channel_same_day(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)])  # 5.000 storefront
    await _open_shift(client, headers)
    await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")  # 5.000

    r = await _get_revenue(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["by_day"]) == 1
    day = data["by_day"][0]
    assert day["order_count"] == 2
    assert day["gross_sales"] == "10.000"
    assert day["storefront_sales"] == "5.000"
    assert day["pos_sales"] == "5.000"
    # both orders are the same product -> one rolled-up product row
    assert len(data["top_products"]) == 1
    assert data["top_products"][0]["qty_sold"] == 2
    assert data["top_products"][0]["gross_sales"] == "10.000"


# ---------------------------------------------------------------------------
# Time buckets
# ---------------------------------------------------------------------------


async def test_multiple_days_ordered_ascending(client: AsyncClient, db: AsyncSession):
    headers, slug, pid = await _setup(client)
    order_a = await _submit_storefront_order(client, slug, items=[_line(pid, 1)])  # 5.000
    await _submit_storefront_order(client, slug, items=[_line(pid, 2)])  # 10.000 (today)
    # Move order A two full days back so it lands in an earlier day bucket.
    await _backdate_order(db, order_a["id"], datetime.now(UTC) - timedelta(days=2))

    r = await _get_revenue(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["by_day"]) == 2
    dates = [p["date"] for p in data["by_day"]]
    assert dates == sorted(dates)  # ascending by date
    assert data["by_day"][0]["gross_sales"] == "5.000"  # earliest = backdated order A
    assert data["by_day"][1]["gross_sales"] == "10.000"  # latest = today's order B


# ---------------------------------------------------------------------------
# Top products: ordering, limit, aggregation
# ---------------------------------------------------------------------------


async def test_top_products_ordered_desc_and_limited_to_10(client: AsyncClient):
    headers, slug, _pid = await _setup(client)
    # 11 products priced 1.000 .. 11.000; one storefront order (qty 1) each.
    created: list[tuple[int, str]] = []
    for i in range(1, 12):
        pid = await _create_product(client, headers, f"P{i}-{_uid()}", f"{i}.000")
        await _submit_storefront_order(client, slug, items=[_line(pid, 1)])
        created.append((i, pid))

    r = await _get_revenue(client, headers)
    assert r.status_code == 200, r.text
    top = r.json()["top_products"]
    assert len(top) == 10
    # gross_sales strictly descending: 11.000 down to 2.000
    assert [p["gross_sales"] for p in top] == [f"{i}.000" for i in range(11, 1, -1)]
    # the cheapest product (1.000) is dropped by LIMIT 10
    returned_ids = {p["product_id"] for p in top}
    cheapest_id = created[0][1]
    assert cheapest_id not in returned_ids


async def test_same_product_summed_across_orders(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)])  # 5.000
    await _submit_storefront_order(client, slug, items=[_line(pid, 2)])  # 10.000
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)])  # 5.000

    r = await _get_revenue(client, headers)
    assert r.status_code == 200, r.text
    top = r.json()["top_products"]
    assert len(top) == 1
    assert top[0]["product_id"] == pid
    assert top[0]["qty_sold"] == 4
    assert top[0]["gross_sales"] == "20.000"


async def test_multi_line_order_creates_separate_product_rows(client: AsyncClient):
    headers, slug, pid_a = await _setup(client)
    pid_b = await _create_product(client, headers, f"ProdB-{_uid()}", "3.000")
    await _submit_storefront_order(
        client, slug, items=[_line(pid_a, 2), _line(pid_b, 1)]
    )  # A: 10.000, B: 3.000

    r = await _get_revenue(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    rows = {p["product_id"]: p for p in data["top_products"]}
    assert len(rows) == 2
    assert rows[pid_a]["qty_sold"] == 2
    assert rows[pid_a]["gross_sales"] == "10.000"
    assert rows[pid_b]["qty_sold"] == 1
    assert rows[pid_b]["gross_sales"] == "3.000"
    # ordered by revenue desc: A (10.000) before B (3.000)
    assert [p["product_id"] for p in data["top_products"]] == [pid_a, pid_b]
    # single order -> single day bucket, total 13.000
    assert len(data["by_day"]) == 1
    assert data["by_day"][0]["gross_sales"] == "13.000"


# ---------------------------------------------------------------------------
# Cancelled handling
# ---------------------------------------------------------------------------


async def test_cancelled_excluded(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)])  # 5.000 non-cancelled
    await _open_shift(client, headers)
    pos = await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")
    await _cancel_pos_order(client, headers, pos["id"])  # -> cancelled

    r = await _get_revenue(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    # by_day excludes the cancelled POS order
    assert len(data["by_day"]) == 1
    day = data["by_day"][0]
    assert day["order_count"] == 1
    assert day["gross_sales"] == "5.000"
    assert day["storefront_sales"] == "5.000"
    assert day["pos_sales"] == "0.000"
    # top_products only counts the non-cancelled storefront line
    assert len(data["top_products"]) == 1
    assert data["top_products"][0]["qty_sold"] == 1
    assert data["top_products"][0]["gross_sales"] == "5.000"


# ---------------------------------------------------------------------------
# Shipping reconciliation (locks the by_day-includes / top_products-excludes rule)
# ---------------------------------------------------------------------------


async def test_shipping_included_in_by_day_excluded_from_top_products(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _set_shipping(client, headers, "kwt", "Kuwait City", "1.500")
    order = await _submit_storefront_order(
        client, slug, items=[_line(pid, 2)], shipping_method_id="kwt"
    )
    assert order["total_amount"] == "11.500"  # 5.000 * 2 + 1.500 shipping
    assert order["shipping_fee"] == "1.500"

    r = await _get_revenue(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    # by_day uses order.total_amount -> includes the 1.500 fee
    day = data["by_day"][0]
    assert day["gross_sales"] == "11.500"
    assert day["storefront_sales"] == "11.500"
    # top_products uses line subtotal -> excludes shipping
    prod = data["top_products"][0]
    assert prod["product_id"] == pid
    assert prod["qty_sold"] == 2
    assert prod["gross_sales"] == "10.000"


# ---------------------------------------------------------------------------
# Date range
# ---------------------------------------------------------------------------


async def test_date_range_excludes_out_of_range_orders(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)])  # created "now"

    today = date.today()
    past_qs = f"from={today - timedelta(days=30)}&to={today - timedelta(days=20)}"
    r = await _get_revenue(client, headers, qs=past_qs)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["by_day"] == []
    assert data["top_products"] == []

    # The same order is counted within the current window
    r = await _get_revenue(client, headers)
    data = r.json()
    assert len(data["by_day"]) == 1
    assert len(data["top_products"]) == 1


async def test_to_not_after_from_returns_422(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    today = date.today()
    r = await _get_revenue(client, headers, qs=f"from={today}&to={today}")
    assert r.status_code == 422
    r = await _get_revenue(client, headers, qs=f"from={today}&to={today - timedelta(days=1)}")
    assert r.status_code == 422


async def test_range_over_180_days_returns_422(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    today = date.today()
    qs = f"from={today - timedelta(days=200)}&to={today}"
    r = await _get_revenue(client, headers, qs=qs)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Auth / role
# ---------------------------------------------------------------------------


async def test_member_role_allowed(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)])
    member_headers = await _invite(client, headers, "member")

    r = await _get_revenue(client, member_headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["by_day"]) == 1


async def test_cashier_role_forbidden(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    cashier_headers = await _invite(client, headers, "cashier")

    r = await _get_revenue(client, cashier_headers)
    assert r.status_code == 403


async def test_unauthenticated_returns_401(client: AsyncClient):
    r = await client.get(f"/api/v1/tenants/me/analytics/revenue?{_valid_range_qs()}")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


async def test_cross_tenant_isolation(client: AsyncClient):
    headers_a, slug_a, pid_a = await _setup(client)
    await _submit_storefront_order(client, slug_a, items=[_line(pid_a, 1)])  # tenant A: 5.000

    headers_b, _slug_b, _pid_b = await _setup(client)  # tenant B: no orders

    r = await _get_revenue(client, headers_b)
    assert r.status_code == 200, r.text
    data_b = r.json()
    assert data_b["by_day"] == []
    assert data_b["top_products"] == []

    r = await _get_revenue(client, headers_a)
    assert len(r.json()["by_day"]) == 1


# ---------------------------------------------------------------------------
# Regression: M13.1 /analytics/sales and the funnel /analytics/summary still work
# ---------------------------------------------------------------------------


async def test_analytics_sales_and_summary_still_work(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)])
    qs = _valid_range_qs()

    r = await client.get(f"/api/v1/tenants/me/analytics/sales?{qs}", headers=headers)
    assert r.status_code == 200, r.text
    sales = r.json()
    for field in ("currency", "total_sales", "total_orders", "by_channel"):
        assert field in sales
    assert sales["total_orders"] == 1
    assert sales["total_sales"] == "5.000"

    r = await client.get(f"/api/v1/tenants/me/analytics/summary?{qs}", headers=headers)
    assert r.status_code == 200, r.text
    summary = r.json()
    for field in ("visitors", "sessions", "event_counts", "funnel"):
        assert field in summary
