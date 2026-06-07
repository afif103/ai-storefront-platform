"""M13.1 backend tests: unified online + POS sales reporting (dashboard-only).

Revenue rule (confirmed): status != 'cancelled' counts as revenue; cancelled
orders are excluded from revenue/AOV and reported separately. Storefront pending
orders count as revenue for M13.1. All assertions are scoped to records created
within each test (every test uses its own fresh tenant), so the persistent dev DB
and cross-test accumulation do not affect results.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient

from tests.conftest import auth_headers

SALES_FIELDS = [
    "currency",
    "total_sales",
    "total_orders",
    "average_order_value",
    "storefront_sales",
    "storefront_orders",
    "pos_sales",
    "pos_orders",
    "cancelled_orders",
    "cancelled_amount",
    "by_channel",
    "by_payment_method",
]


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _valid_range_qs() -> str:
    """A wide, valid range that includes 'now' orders (mirrors the analytics test)."""
    today = date.today()
    return f"from={today - timedelta(days=7)}&to={today + timedelta(days=1)}"


async def _setup(client: AsyncClient) -> tuple[dict, str, str]:
    """Create tenant + a 5.000-priced active product. Return (headers, slug, product_id)."""
    uid = _uid()
    headers = auth_headers(sub=f"sr-{uid}", email=f"sr-{uid}@test.com")
    headers["Content-Type"] = "application/json"
    slug = f"sr-{uid}"
    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"SR {uid}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"SRProd-{uid}",
            "price_amount": "5.000",
            "is_active": True,
            "stock_qty": 1000,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return headers, slug, r.json()["id"]


async def _submit_storefront_order(
    client: AsyncClient,
    slug: str,
    product_id: str,
    *,
    qty: int = 1,
    payment_method: str | None = None,
) -> dict:
    body: dict = {
        "customer_name": "Buyer",
        "customer_email": f"buyer-{_uid()}@e.com",
        "items": [{"catalog_item_id": product_id, "qty": qty}],
    }
    if payment_method is not None:
        body["payment_method"] = payment_method
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
    product_id: str,
    *,
    qty: int = 1,
    payment_method: str | None = None,
) -> dict:
    body: dict = {"items": [{"catalog_item_id": product_id, "qty": qty}]}
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
    email = f"srm-{uid}@test.com"
    r = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": email, "role": role},
        headers=owner_headers,
    )
    assert r.status_code == 201, r.text
    member_headers = auth_headers(sub=f"srm-{uid}", email=email)
    member_headers["Content-Type"] = "application/json"
    r = await client.post("/api/v1/auth/accept-invite", headers=member_headers)
    assert r.status_code == 200, r.text
    return member_headers


async def _get_sales(client: AsyncClient, headers: dict, qs: str | None = None):
    qs = qs if qs is not None else _valid_range_qs()
    return await client.get(f"/api/v1/tenants/me/analytics/sales?{qs}", headers=headers)


# ---------------------------------------------------------------------------
# Empty / shape
# ---------------------------------------------------------------------------


async def test_empty_report_returns_zeros(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    r = await _get_sales(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    for field in SALES_FIELDS:
        assert field in data
    assert data["currency"] == "KWD"
    assert data["total_sales"] == "0.000"
    assert data["total_orders"] == 0
    assert data["average_order_value"] == "0.000"
    assert data["storefront_sales"] == "0.000"
    assert data["storefront_orders"] == 0
    assert data["pos_sales"] == "0.000"
    assert data["pos_orders"] == 0
    assert data["cancelled_orders"] == 0
    assert data["cancelled_amount"] == "0.000"
    assert data["by_channel"] == []
    assert data["by_payment_method"] == []


# ---------------------------------------------------------------------------
# Channel contributions
# ---------------------------------------------------------------------------


async def test_storefront_order_contributes_to_revenue(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    order = await _submit_storefront_order(client, slug, pid)

    r = await _get_sales(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["currency"] == order["currency"]
    assert data["total_sales"] == "5.000"
    assert data["total_orders"] == 1
    assert data["storefront_sales"] == "5.000"
    assert data["storefront_orders"] == 1
    assert data["pos_sales"] == "0.000"
    assert data["pos_orders"] == 0
    assert data["by_channel"] == [
        {"source": "storefront", "order_count": 1, "gross_sales": "5.000"}
    ]


async def test_pos_order_contributes_to_revenue(client: AsyncClient):
    headers, _slug, pid = await _setup(client)
    await _open_shift(client, headers)
    pos_order = await _create_pos_order(client, headers, pid, payment_method="cash")

    r = await _get_sales(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["currency"] == pos_order["currency"]
    assert data["total_sales"] == "5.000"
    assert data["total_orders"] == 1
    assert data["pos_sales"] == "5.000"
    assert data["pos_orders"] == 1
    assert data["storefront_sales"] == "0.000"
    assert data["storefront_orders"] == 0
    assert data["by_channel"] == [{"source": "pos", "order_count": 1, "gross_sales": "5.000"}]


async def test_mixed_storefront_and_pos_totals_and_channels(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    sf = await _submit_storefront_order(client, slug, pid)  # 5.000
    await _open_shift(client, headers)
    await _create_pos_order(client, headers, pid, payment_method="cash")  # 5.000
    await _create_pos_order(client, headers, pid, payment_method="cash")  # 5.000

    r = await _get_sales(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["currency"] == sf["currency"]
    assert data["total_sales"] == "15.000"
    assert data["total_orders"] == 3
    assert data["storefront_sales"] == "5.000"
    assert data["storefront_orders"] == 1
    assert data["pos_sales"] == "10.000"
    assert data["pos_orders"] == 2
    # by_channel ordered by source: pos, storefront
    channels = {c["source"]: c for c in data["by_channel"]}
    assert channels["storefront"] == {
        "source": "storefront",
        "order_count": 1,
        "gross_sales": "5.000",
    }
    assert channels["pos"] == {"source": "pos", "order_count": 2, "gross_sales": "10.000"}


# ---------------------------------------------------------------------------
# Cancelled handling
# ---------------------------------------------------------------------------


async def test_cancelled_excluded_from_revenue_counted_separately(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, pid)  # 5.000 non-cancelled
    await _open_shift(client, headers)
    pos_order = await _create_pos_order(client, headers, pid, payment_method="cash")
    await _cancel_pos_order(client, headers, pos_order["id"])  # -> cancelled

    r = await _get_sales(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    # Revenue excludes the cancelled POS order
    assert data["total_sales"] == "5.000"
    assert data["total_orders"] == 1
    assert data["storefront_sales"] == "5.000"
    assert data["storefront_orders"] == 1
    assert data["pos_sales"] == "0.000"
    assert data["pos_orders"] == 0
    # Cancelled reported separately
    assert data["cancelled_orders"] == 1
    assert data["cancelled_amount"] == "5.000"
    # AOV over non-cancelled only
    assert data["average_order_value"] == "5.000"
    # cancelled POS order absent from channel breakdown
    assert [c["source"] for c in data["by_channel"]] == ["storefront"]


# ---------------------------------------------------------------------------
# Average order value
# ---------------------------------------------------------------------------


async def test_average_order_value_three_decimals(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, pid, qty=1)  # 5.000
    await _submit_storefront_order(client, slug, pid, qty=2)  # 10.000
    await _submit_storefront_order(client, slug, pid, qty=1)  # 5.000

    r = await _get_sales(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_sales"] == "20.000"
    assert data["total_orders"] == 3
    # 20.000 / 3 -> 6.667 (quantized to 3 decimals)
    assert data["average_order_value"] == "6.667"
    expected = (Decimal(data["total_sales"]) / Decimal(data["total_orders"])).quantize(
        Decimal("0.001")
    )
    assert data["average_order_value"] == str(expected)


async def test_aov_zero_when_no_non_cancelled_orders(client: AsyncClient):
    headers, _slug, pid = await _setup(client)
    await _open_shift(client, headers)
    pos_order = await _create_pos_order(client, headers, pid)
    await _cancel_pos_order(client, headers, pos_order["id"])  # only a cancelled order

    r = await _get_sales(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_orders"] == 0
    assert data["total_sales"] == "0.000"
    assert data["average_order_value"] == "0.000"
    assert data["cancelled_orders"] == 1
    assert data["cancelled_amount"] == "5.000"
    assert data["by_channel"] == []


# ---------------------------------------------------------------------------
# Payment-method breakdown
# ---------------------------------------------------------------------------


async def test_payment_method_breakdown_includes_null_bucket(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, pid)  # no payment_method -> NULL
    await _open_shift(client, headers)
    await _create_pos_order(client, headers, pid, payment_method="cash")
    await _create_pos_order(client, headers, pid, payment_method="knet")

    r = await _get_sales(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    buckets = {e["payment_method"]: e for e in data["by_payment_method"]}
    assert buckets["cash"]["order_count"] == 1
    assert buckets["cash"]["gross_sales"] == "5.000"
    assert buckets["knet"]["order_count"] == 1
    assert buckets["knet"]["gross_sales"] == "5.000"
    # NULL payment_method preserved as JSON null (Python None key)
    assert None in buckets
    assert buckets[None]["order_count"] == 1
    assert buckets[None]["gross_sales"] == "5.000"


# ---------------------------------------------------------------------------
# Date range
# ---------------------------------------------------------------------------


async def test_date_range_excludes_out_of_range_orders(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, pid)  # created "now"

    today = date.today()
    # A valid past window that ends before today -> the order is excluded
    past_qs = f"from={today - timedelta(days=30)}&to={today - timedelta(days=20)}"
    r = await _get_sales(client, headers, qs=past_qs)
    assert r.status_code == 200, r.text
    assert r.json()["total_orders"] == 0

    # The same order is counted within the current window
    r = await _get_sales(client, headers)
    assert r.json()["total_orders"] == 1


async def test_to_not_after_from_returns_422(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    today = date.today()
    r = await _get_sales(client, headers, qs=f"from={today}&to={today}")
    assert r.status_code == 422
    r = await _get_sales(client, headers, qs=f"from={today}&to={today - timedelta(days=1)}")
    assert r.status_code == 422


async def test_range_over_180_days_returns_422(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    today = date.today()
    qs = f"from={today - timedelta(days=200)}&to={today}"
    r = await _get_sales(client, headers, qs=qs)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Auth / role
# ---------------------------------------------------------------------------


async def test_member_role_allowed(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, pid)
    member_headers = await _invite(client, headers, "member")

    r = await _get_sales(client, member_headers)
    assert r.status_code == 200, r.text
    assert r.json()["total_orders"] == 1


async def test_cashier_role_forbidden(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    cashier_headers = await _invite(client, headers, "cashier")

    r = await _get_sales(client, cashier_headers)
    assert r.status_code == 403


async def test_unauthenticated_returns_401(client: AsyncClient):
    r = await client.get(f"/api/v1/tenants/me/analytics/sales?{_valid_range_qs()}")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


async def test_cross_tenant_isolation(client: AsyncClient):
    headers_a, slug_a, pid_a = await _setup(client)
    await _submit_storefront_order(client, slug_a, pid_a)  # tenant A: 5.000

    headers_b, _slug_b, _pid_b = await _setup(client)  # tenant B: no orders

    # Tenant B's report does not see tenant A's order
    r = await _get_sales(client, headers_b)
    assert r.status_code == 200, r.text
    data_b = r.json()
    assert data_b["total_orders"] == 0
    assert data_b["total_sales"] == "0.000"
    assert data_b["by_channel"] == []

    # Tenant A still sees its own order
    r = await _get_sales(client, headers_a)
    assert r.json()["total_orders"] == 1


# ---------------------------------------------------------------------------
# Regression: existing /analytics/summary endpoint still works
# ---------------------------------------------------------------------------


async def test_analytics_summary_still_works(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    r = await client.get(
        f"/api/v1/tenants/me/analytics/summary?{_valid_range_qs()}", headers=headers
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # Shape unchanged
    for field in ("visitors", "sessions", "event_counts", "funnel"):
        assert field in data
