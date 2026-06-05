"""POS shift open/close + cash-summary tests (M12.3)."""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from tests.conftest import auth_headers

pytestmark = pytest.mark.pos


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _setup(client: AsyncClient, *, stock_qty: int = 50) -> tuple[dict, str]:
    # Create tenant + product (owner headers), return (headers, product_id).
    uid = _uid()
    headers = auth_headers(sub=f"shift-{uid}", email=f"shift-{uid}@test.com")
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"Shift {uid}", "slug": f"shift-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"Item-{uid}",
            "price_amount": "5.000",
            "is_active": True,
            "track_inventory": True,
            "stock_qty": stock_qty,
        },
        headers=headers,
    )
    assert r.status_code == 201
    return headers, r.json()["id"]


async def _open(client: AsyncClient, headers: dict, starting_cash: str = "10.000"):
    return await client.post(
        "/api/v1/tenants/me/pos/shifts/open",
        json={"starting_cash": starting_cash},
        headers=headers,
    )


async def _close(client: AsyncClient, headers: dict, counted_cash: str):
    return await client.post(
        "/api/v1/tenants/me/pos/shifts/close",
        json={"counted_cash": counted_cash},
        headers=headers,
    )


async def _current(client: AsyncClient, headers: dict):
    return await client.get("/api/v1/tenants/me/pos/shifts/current", headers=headers)


async def _sale(
    client: AsyncClient,
    headers: dict,
    product_id: str,
    *,
    qty: int = 1,
    payment_method: str | None = "cash",
):
    body: dict = {"items": [{"catalog_item_id": product_id, "qty": qty}]}
    if payment_method is not None:
        body["payment_method"] = payment_method
    return await client.post("/api/v1/tenants/me/pos/orders", json=body, headers=headers)


async def test_open_shift_success(client: AsyncClient):
    headers, _pid = await _setup(client)

    r = await _open(client, headers, "10.000")
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "open"
    assert Decimal(data["starting_cash"]) == Decimal("10.000")
    assert Decimal(data["cash_sales"]) == Decimal("0")
    assert Decimal(data["expected_cash"]) == Decimal("10.000")
    assert data["opened_by"] is not None
    assert data["closed_at"] is None


async def test_open_shift_when_already_open_returns_409(client: AsyncClient):
    headers, _pid = await _setup(client)

    assert (await _open(client, headers)).status_code == 201
    r = await _open(client, headers)
    assert r.status_code == 409


async def test_current_shift_when_none(client: AsyncClient):
    headers, _pid = await _setup(client)

    r = await _current(client, headers)
    assert r.status_code == 200
    assert r.json()["shift"] is None


async def test_current_shift_when_open_reports_live_cash_sales(client: AsyncClient):
    headers, pid = await _setup(client)
    await _open(client, headers, "10.000")

    r = await _sale(client, headers, pid, qty=2, payment_method="cash")  # 2 * 5 = 10
    assert r.status_code == 201

    shift = (await _current(client, headers)).json()["shift"]
    assert shift is not None
    assert Decimal(shift["starting_cash"]) == Decimal("10.000")
    assert Decimal(shift["cash_sales"]) == Decimal("10.000")
    assert Decimal(shift["expected_cash"]) == Decimal("20.000")


async def test_pos_order_without_open_shift_returns_409(client: AsyncClient):
    headers, pid = await _setup(client)

    r = await _sale(client, headers, pid, qty=1)
    assert r.status_code == 409


async def test_cash_order_with_open_shift_sets_shift_id_and_counts(
    client: AsyncClient, db: AsyncSession
):
    headers, pid = await _setup(client)
    shift_id = (await _open(client, headers, "0.000")).json()["id"]

    r = await _sale(client, headers, pid, qty=3, payment_method="cash")  # 15
    assert r.status_code == 201
    order_id = r.json()["id"]

    order = await db.get(Order, uuid.UUID(order_id))
    assert order is not None
    assert str(order.shift_id) == shift_id

    shift = (await _current(client, headers)).json()["shift"]
    assert Decimal(shift["cash_sales"]) == Decimal("15.000")


async def test_non_cash_order_is_associated_but_excluded_from_cash(client: AsyncClient):
    headers, pid = await _setup(client)
    await _open(client, headers, "0.000")

    r = await _sale(client, headers, pid, qty=2, payment_method="knet")
    assert r.status_code == 201

    shift = (await _current(client, headers)).json()["shift"]
    assert Decimal(shift["cash_sales"]) == Decimal("0")


async def test_cancelled_cash_order_excluded_from_cash_sales(client: AsyncClient):
    headers, pid = await _setup(client)
    await _open(client, headers, "0.000")

    r = await _sale(client, headers, pid, qty=2, payment_method="cash")
    assert r.status_code == 201
    order_id = r.json()["id"]

    shift = (await _current(client, headers)).json()["shift"]
    assert Decimal(shift["cash_sales"]) == Decimal("10.000")

    rc = await client.patch(f"/api/v1/tenants/me/pos/orders/{order_id}/cancel", headers=headers)
    assert rc.status_code == 200

    shift = (await _current(client, headers)).json()["shift"]
    assert Decimal(shift["cash_sales"]) == Decimal("0")


async def test_close_shift_success(client: AsyncClient):
    headers, pid = await _setup(client)
    await _open(client, headers, "10.000")

    r = await _sale(client, headers, pid, qty=2, payment_method="cash")  # 10
    assert r.status_code == 201

    r = await _close(client, headers, "19.500")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "closed"
    assert Decimal(data["cash_sales"]) == Decimal("10.000")
    assert Decimal(data["expected_cash"]) == Decimal("20.000")
    assert Decimal(data["counted_cash"]) == Decimal("19.500")
    assert Decimal(data["variance"]) == Decimal("-0.500")
    assert data["closed_by"] is not None
    assert data["closed_at"] is not None

    assert (await _current(client, headers)).json()["shift"] is None


async def test_close_shift_when_none_returns_409(client: AsyncClient):
    headers, _pid = await _setup(client)

    r = await _close(client, headers, "0.000")
    assert r.status_code == 409


async def test_one_open_shift_per_tenant_then_reopen_after_close(client: AsyncClient):
    headers, _pid = await _setup(client)

    assert (await _open(client, headers, "5.000")).status_code == 201
    assert (await _open(client, headers, "5.000")).status_code == 409
    assert (await _close(client, headers, "5.000")).status_code == 200
    # A fresh shift can be opened once the previous one is closed.
    assert (await _open(client, headers, "5.000")).status_code == 201


async def test_cross_tenant_shift_isolation(client: AsyncClient):
    headers_a, _pid_a = await _setup(client)
    assert (await _open(client, headers_a, "10.000")).status_code == 201

    headers_b, _pid_b = await _setup(client)
    # B has no open shift of its own and cannot see/close A's shift.
    assert (await _current(client, headers_b)).json()["shift"] is None
    assert (await _close(client, headers_b, "0.000")).status_code == 409

    # A's shift is still open and unaffected.
    assert (await _current(client, headers_a)).json()["shift"] is not None
