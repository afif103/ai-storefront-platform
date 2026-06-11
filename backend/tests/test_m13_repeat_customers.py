"""M13.4 backend tests: repeat-customer analytics (new vs returning, B1 semantics).

Read-only `GET /tenants/me/analytics/repeat-customers?from&to`. Identity is
orders.customer_id (find_or_create_customer email-then-phone dedupe); orders
with customer_id IS NULL count only toward anonymous_orders. B1 semantics:
among customers active in the window, 'new' = first-ever non-cancelled order is
inside the window, 'returning' = it predates the window — a customer whose only
orders are 2+ inside the window is still new. Lifetime figures are capped at
the exclusive window end. Non-cancelled only. Every test uses its own fresh
tenant, so assertions are unaffected by the persistent dev DB.
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
    """A recent window that includes 'now' orders (mirrors the analytics tests)."""
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
    headers = auth_headers(sub=f"rpt-{uid}", email=f"rpt-{uid}@test.com")
    headers["Content-Type"] = "application/json"
    slug = f"rpt-{uid}"
    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"RPT {uid}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    pid = await _create_product(client, headers, f"RptProd-{uid}", "5.000")
    return headers, slug, pid


async def _submit_storefront_order(
    client: AsyncClient,
    slug: str,
    *,
    items: list[dict],
    email: str,
    name: str = "Buyer",
) -> dict:
    """Submit a storefront order WITH contact email -> linked to a customer record."""
    body: dict = {"customer_name": name, "customer_email": email, "items": items}
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
    """Create a POS order — contactless by API design, so customer_id is NULL."""
    body: dict = {"items": items}
    if payment_method is not None:
        body["payment_method"] = payment_method
    r = await client.post("/api/v1/tenants/me/pos/orders", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _cancel_order_admin(client: AsyncClient, headers: dict, order_id: str) -> None:
    """Cancel a (pending) storefront order via the admin status-transition endpoint."""
    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert r.status_code == 200, r.text


async def _invite(client: AsyncClient, owner_headers: dict, role: str) -> dict:
    uid = _uid()
    email = f"rptm-{uid}@test.com"
    r = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": email, "role": role},
        headers=owner_headers,
    )
    assert r.status_code == 201, r.text
    member_headers = auth_headers(sub=f"rptm-{uid}", email=email)
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


async def _link_order_to_customer(db: AsyncSession, order_id: str, customer_id: str) -> None:
    """Test-only setup: link an order (e.g. contactless POS) to a customer (committed)."""
    await db.execute(
        text("UPDATE orders SET customer_id = :cid WHERE id = :oid"),
        {"cid": uuid.UUID(customer_id), "oid": uuid.UUID(order_id)},
    )
    await db.commit()


async def _get_repeat(client: AsyncClient, headers: dict, qs: str | None = None):
    qs = qs if qs is not None else _valid_range_qs()
    return await client.get(f"/api/v1/tenants/me/analytics/repeat-customers?{qs}", headers=headers)


# ---------------------------------------------------------------------------
# Empty / shape
# ---------------------------------------------------------------------------


async def test_empty_returns_zeros_and_kwd(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    r = await _get_repeat(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["currency"] == "KWD"
    assert data["identified_customers"] == 0
    assert data["new_customers"] == 0
    assert data["returning_customers"] == 0
    assert data["repeat_rate"] == 0.0
    assert data["anonymous_orders"] == 0
    assert data["top_returning"] == []


# ---------------------------------------------------------------------------
# New vs returning (B1 semantics)
# ---------------------------------------------------------------------------


async def test_single_new_customer(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    order = await _submit_storefront_order(
        client, slug, items=[_line(pid, 1)], email=f"new-{_uid()}@e.com"
    )
    assert order["customer_id"] is not None

    r = await _get_repeat(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["currency"] == order["currency"]
    assert data["identified_customers"] == 1
    assert data["new_customers"] == 1
    assert data["returning_customers"] == 0
    assert data["repeat_rate"] == 0.0
    assert data["anonymous_orders"] == 0
    assert data["top_returning"] == []


async def test_returning_customer_with_pre_window_order(client: AsyncClient, db: AsyncSession):
    headers, slug, pid = await _setup(client)
    email = f"ret-{_uid()}@e.com"
    first = await _submit_storefront_order(client, slug, items=[_line(pid, 1)], email=email)
    ts = datetime.now(UTC) - timedelta(days=40)
    await _backdate_order(db, first["id"], ts)  # first-ever order predates the window
    await _submit_storefront_order(client, slug, items=[_line(pid, 2)], email=email)  # 10.000

    r = await _get_repeat(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["identified_customers"] == 1
    assert data["new_customers"] == 0
    assert data["returning_customers"] == 1
    assert data["repeat_rate"] == 1.0
    assert len(data["top_returning"]) == 1
    row = data["top_returning"][0]
    assert row["customer_id"] == first["customer_id"]
    assert row["orders_in_window"] == 1
    assert row["lifetime_orders"] == 2
    assert row["window_spent"] == "10.000"
    assert row["first_order_date"] == str(ts.date())


async def test_b1_two_in_window_orders_no_history_is_new(client: AsyncClient):
    """B1 lock: 2 in-window orders with no prior history = new customer, not returning."""
    headers, slug, pid = await _setup(client)
    email = f"b1-{_uid()}@e.com"
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)], email=email)
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)], email=email)

    r = await _get_repeat(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["identified_customers"] == 1
    assert data["new_customers"] == 1
    assert data["returning_customers"] == 0
    assert data["repeat_rate"] == 0.0
    assert data["top_returning"] == []


async def test_same_email_dedupe_single_customer(client: AsyncClient):
    """Email is normalized (lowercased) -> case variants link to ONE customer."""
    headers, slug, pid = await _setup(client)
    email = f"dup-{_uid()}@e.com"
    order_a = await _submit_storefront_order(client, slug, items=[_line(pid, 1)], email=email)
    order_b = await _submit_storefront_order(
        client, slug, items=[_line(pid, 1)], email=email.upper()
    )
    assert order_a["customer_id"] == order_b["customer_id"]

    r = await _get_repeat(client, headers)
    assert r.status_code == 200, r.text
    assert r.json()["identified_customers"] == 1


# ---------------------------------------------------------------------------
# Cross-channel + anonymous handling
# ---------------------------------------------------------------------------


async def test_cross_channel_pos_linked_by_customer_id(client: AsyncClient, db: AsyncSession):
    """A POS order DB-linked to a customer counts toward that customer, cross-channel."""
    headers, slug, pid = await _setup(client)
    email = f"xch-{_uid()}@e.com"
    first = await _submit_storefront_order(client, slug, items=[_line(pid, 1)], email=email)
    await _backdate_order(db, first["id"], datetime.now(UTC) - timedelta(days=40))

    await _open_shift(client, headers)
    pos = await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")
    await _link_order_to_customer(db, pos["id"], first["customer_id"])

    r = await _get_repeat(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["identified_customers"] == 1
    assert data["returning_customers"] == 1
    assert data["new_customers"] == 0
    assert data["anonymous_orders"] == 0  # the POS order is linked, not anonymous
    row = data["top_returning"][0]
    assert row["orders_in_window"] == 1  # the in-window POS order
    assert row["lifetime_orders"] == 2
    assert row["window_spent"] == "5.000"


async def test_anonymous_pos_walkin_counted_only_in_anonymous(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)], email=f"a-{_uid()}@e.com")
    await _open_shift(client, headers)
    await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")

    r = await _get_repeat(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["identified_customers"] == 1  # only the storefront customer
    assert data["new_customers"] == 1
    assert data["anonymous_orders"] == 1  # the contactless POS walk-in
    assert data["top_returning"] == []


# ---------------------------------------------------------------------------
# Cancelled handling
# ---------------------------------------------------------------------------


async def test_cancelled_orders_excluded(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)], email=f"k-{_uid()}@e.com")
    victim = await _submit_storefront_order(
        client, slug, items=[_line(pid, 1)], email=f"v-{_uid()}@e.com"
    )
    await _cancel_order_admin(client, headers, victim["id"])  # pending -> cancelled

    r = await _get_repeat(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["identified_customers"] == 1  # the cancelled customer's only order is excluded
    assert data["new_customers"] == 1
    assert data["anonymous_orders"] == 0  # cancelled orders never count as anonymous either


async def test_cancelled_pre_window_order_does_not_make_returning(
    client: AsyncClient, db: AsyncSession
):
    headers, slug, pid = await _setup(client)
    email = f"cpw-{_uid()}@e.com"
    old = await _submit_storefront_order(client, slug, items=[_line(pid, 1)], email=email)
    await _cancel_order_admin(client, headers, old["id"])
    await _backdate_order(db, old["id"], datetime.now(UTC) - timedelta(days=40))
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)], email=email)

    r = await _get_repeat(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    # The cancelled pre-window order must not set first_order_date / returning status.
    assert data["identified_customers"] == 1
    assert data["new_customers"] == 1
    assert data["returning_customers"] == 0
    assert data["top_returning"] == []


# ---------------------------------------------------------------------------
# Top returning: ordering + LIMIT 5
# ---------------------------------------------------------------------------


async def test_top_returning_ordering_and_limit_5(client: AsyncClient, db: AsyncSession):
    headers, slug, pid = await _setup(client)
    ts = datetime.now(UTC) - timedelta(days=40)
    created: list[tuple[int, str]] = []
    # 6 returning customers; equal orders_in_window (1) -> ordered by window_spent desc.
    for i in range(1, 7):
        email = f"top{i}-{_uid()}@e.com"
        old = await _submit_storefront_order(client, slug, items=[_line(pid, 1)], email=email)
        await _backdate_order(db, old["id"], ts)
        await _submit_storefront_order(client, slug, items=[_line(pid, i)], email=email)
        created.append((i, old["customer_id"]))

    r = await _get_repeat(client, headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["identified_customers"] == 6
    assert data["returning_customers"] == 6
    assert data["new_customers"] == 0
    assert data["repeat_rate"] == 1.0
    top = data["top_returning"]
    assert len(top) == 5
    # window_spent strictly descending: 30.000 down to 10.000
    assert [row["window_spent"] for row in top] == [f"{i * 5}.000" for i in range(6, 1, -1)]
    # the lowest-spend returning customer (5.000) is dropped by LIMIT 5
    returned_ids = {row["customer_id"] for row in top}
    assert created[0][1] not in returned_ids


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def test_to_not_after_from_returns_422(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    today = date.today()
    r = await _get_repeat(client, headers, qs=f"from={today}&to={today}")
    assert r.status_code == 422
    r = await _get_repeat(client, headers, qs=f"from={today}&to={today - timedelta(days=1)}")
    assert r.status_code == 422


async def test_range_over_180_days_returns_422(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    today = date.today()
    r = await _get_repeat(client, headers, qs=f"from={today - timedelta(days=200)}&to={today}")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Auth / role
# ---------------------------------------------------------------------------


async def test_member_role_allowed(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)], email=f"m-{_uid()}@e.com")
    member_headers = await _invite(client, headers, "member")

    r = await _get_repeat(client, member_headers)
    assert r.status_code == 200, r.text
    assert r.json()["identified_customers"] == 1


async def test_cashier_role_forbidden(client: AsyncClient):
    headers, _slug, _pid = await _setup(client)
    cashier_headers = await _invite(client, headers, "cashier")

    r = await _get_repeat(client, cashier_headers)
    assert r.status_code == 403


async def test_unauthenticated_returns_401(client: AsyncClient):
    r = await client.get(f"/api/v1/tenants/me/analytics/repeat-customers?{_valid_range_qs()}")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


async def test_cross_tenant_isolation(client: AsyncClient):
    headers_a, slug_a, pid_a = await _setup(client)
    await _submit_storefront_order(
        client, slug_a, items=[_line(pid_a, 1)], email=f"iso-{_uid()}@e.com"
    )

    headers_b, _slug_b, _pid_b = await _setup(client)  # tenant B: no orders

    r = await _get_repeat(client, headers_b)
    assert r.status_code == 200, r.text
    data_b = r.json()
    assert data_b["identified_customers"] == 0
    assert data_b["anonymous_orders"] == 0
    assert data_b["top_returning"] == []

    r = await _get_repeat(client, headers_a)
    assert r.json()["identified_customers"] == 1


# ---------------------------------------------------------------------------
# Regression: sales / revenue / pos-today / summary still respond
# ---------------------------------------------------------------------------


async def test_existing_analytics_endpoints_still_respond(client: AsyncClient):
    headers, slug, pid = await _setup(client)
    await _submit_storefront_order(client, slug, items=[_line(pid, 1)], email=f"r-{_uid()}@e.com")
    await _open_shift(client, headers)
    await _create_pos_order(client, headers, items=[_line(pid, 1)], payment_method="cash")
    qs = _valid_range_qs()

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

    r = await client.get(
        f"/api/v1/tenants/me/analytics/pos-today?date={date.today()}", headers=headers
    )
    assert r.status_code == 200, r.text
    pos_today = r.json()
    assert pos_today["pos_order_count"] == 1
    assert pos_today["pos_sales"] == "5.000"

    r = await client.get(f"/api/v1/tenants/me/analytics/summary?{qs}", headers=headers)
    assert r.status_code == 200, r.text
    summary = r.json()
    for field in ("visitors", "sessions", "event_counts", "funnel"):
        assert field in summary
