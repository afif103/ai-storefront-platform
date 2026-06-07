"""M12.7 backend tests: customer order-history endpoint (dashboard-only)."""

import uuid

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers

ORDER_FIELDS = [
    "id",
    "order_number",
    "source",
    "status",
    "total_amount",
    "currency",
    "fulfillment_status",
]


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _setup(client: AsyncClient) -> tuple[dict, str, str]:
    """Create tenant + product. Return (headers, slug, product_id)."""
    uid = _uid()
    headers = auth_headers(sub=f"co-{uid}", email=f"co-{uid}@test.com")
    headers["Content-Type"] = "application/json"
    slug = f"co-{uid}"
    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"CO {uid}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"COProd-{uid}",
            "price_amount": "5.000",
            "is_active": True,
            "stock_qty": 100,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return headers, slug, r.json()["id"]


async def _submit_storefront_order(
    client: AsyncClient, slug: str, product_id: str, email: str
) -> dict:
    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Buyer",
            "customer_email": email,
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_customer(client: AsyncClient, headers: dict, email: str) -> dict:
    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Cust", "email": email},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _open_shift(client: AsyncClient, headers: dict) -> None:
    r = await client.post(
        "/api/v1/tenants/me/pos/shifts/open",
        json={"starting_cash": "0.000"},
        headers=headers,
    )
    assert r.status_code == 201, r.text


async def _create_pos_order(client: AsyncClient, headers: dict, product_id: str) -> dict:
    r = await client.post(
        "/api/v1/tenants/me/pos/orders",
        json={"items": [{"catalog_item_id": product_id, "qty": 1}]},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _invite_member(client: AsyncClient, owner_headers: dict) -> dict:
    uid = _uid()
    member_email = f"comem-{uid}@test.com"
    r = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": member_email, "role": "member"},
        headers=owner_headers,
    )
    assert r.status_code == 201, r.text
    member_headers = auth_headers(sub=f"comem-{uid}", email=member_email)
    member_headers["Content-Type"] = "application/json"
    r = await client.post("/api/v1/auth/accept-invite", headers=member_headers)
    assert r.status_code == 200, r.text
    return member_headers


async def _link_order_to_customer(db: AsyncSession, order_id: str, customer_id: str) -> None:
    """Test-only setup: link an order (e.g. a POS Walk-in) to a customer at the DB layer."""
    await db.execute(
        text("UPDATE orders SET customer_id = :cid WHERE id = :oid"),
        {"cid": uuid.UUID(customer_id), "oid": uuid.UUID(order_id)},
    )
    await db.commit()


async def _get_customer_orders(client: AsyncClient, headers: dict, customer_id: str):
    return await client.get(f"/api/v1/tenants/me/customers/{customer_id}/orders", headers=headers)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


async def test_storefront_order_listed_for_customer(client: AsyncClient):
    headers, slug, product_id = await _setup(client)
    order = await _submit_storefront_order(client, slug, product_id, f"sf-{_uid()}@e.com")
    customer_id = order["customer_id"]
    assert customer_id is not None

    r = await _get_customer_orders(client, headers, customer_id)
    assert r.status_code == 200
    rows = r.json()
    assert [o["id"] for o in rows] == [order["id"]]
    assert rows[0]["source"] == "storefront"
    for field in ORDER_FIELDS:
        assert field in rows[0]


async def test_pos_order_listed_for_customer_after_db_link(client: AsyncClient, db: AsyncSession):
    headers, _slug, product_id = await _setup(client)
    customer = await _create_customer(client, headers, f"pos-{_uid()}@e.com")
    customer_id = customer["id"]

    await _open_shift(client, headers)
    pos_order = await _create_pos_order(client, headers, product_id)
    assert pos_order["source"] == "pos"
    assert pos_order["customer_id"] is None  # POS is contactless by API design

    await _link_order_to_customer(db, pos_order["id"], customer_id)

    r = await _get_customer_orders(client, headers, customer_id)
    assert r.status_code == 200
    rows = r.json()
    assert [o["id"] for o in rows] == [pos_order["id"]]
    assert rows[0]["source"] == "pos"


async def test_storefront_and_pos_both_newest_first(client: AsyncClient, db: AsyncSession):
    headers, slug, product_id = await _setup(client)
    storefront = await _submit_storefront_order(client, slug, product_id, f"both-{_uid()}@e.com")
    customer_id = storefront["customer_id"]
    assert customer_id is not None

    await _open_shift(client, headers)
    pos_order = await _create_pos_order(client, headers, product_id)
    await _link_order_to_customer(db, pos_order["id"], customer_id)

    r = await _get_customer_orders(client, headers, customer_id)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    # POS order was created after the storefront order -> newest first.
    assert rows[0]["id"] == pos_order["id"]
    assert rows[0]["source"] == "pos"
    assert rows[1]["id"] == storefront["id"]
    assert rows[1]["source"] == "storefront"


# ---------------------------------------------------------------------------
# Isolation / edge cases
# ---------------------------------------------------------------------------


async def test_other_customers_orders_excluded(client: AsyncClient):
    headers, slug, product_id = await _setup(client)
    order_a = await _submit_storefront_order(client, slug, product_id, f"a-{_uid()}@e.com")
    order_b = await _submit_storefront_order(client, slug, product_id, f"b-{_uid()}@e.com")
    assert order_a["customer_id"] != order_b["customer_id"]

    r = await _get_customer_orders(client, headers, order_a["customer_id"])
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()]
    assert ids == [order_a["id"]]
    assert order_b["id"] not in ids


async def test_customer_with_no_orders_returns_empty(client: AsyncClient):
    headers, _slug, _product_id = await _setup(client)
    customer = await _create_customer(client, headers, f"empty-{_uid()}@e.com")
    r = await _get_customer_orders(client, headers, customer["id"])
    assert r.status_code == 200
    assert r.json() == []


async def test_unknown_customer_returns_404(client: AsyncClient):
    headers, _slug, _product_id = await _setup(client)
    r = await _get_customer_orders(client, headers, str(uuid.uuid4()))
    assert r.status_code == 404


async def test_cross_tenant_customer_returns_404(client: AsyncClient):
    headers_a, slug_a, product_id_a = await _setup(client)
    order_a = await _submit_storefront_order(client, slug_a, product_id_a, f"xt-{_uid()}@e.com")
    customer_id_a = order_a["customer_id"]

    headers_b, _slug_b, _product_id_b = await _setup(client)
    r = await _get_customer_orders(client, headers_b, customer_id_a)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Auth / role
# ---------------------------------------------------------------------------


async def test_member_role_can_list_customer_orders(client: AsyncClient):
    headers, slug, product_id = await _setup(client)
    order = await _submit_storefront_order(client, slug, product_id, f"mem-{_uid()}@e.com")
    member_headers = await _invite_member(client, headers)

    r = await _get_customer_orders(client, member_headers, order["customer_id"])
    assert r.status_code == 200
    assert [o["id"] for o in r.json()] == [order["id"]]


async def test_unauthenticated_returns_401(client: AsyncClient):
    headers, slug, product_id = await _setup(client)
    order = await _submit_storefront_order(client, slug, product_id, f"un-{_uid()}@e.com")
    r = await client.get(f"/api/v1/tenants/me/customers/{order['customer_id']}/orders")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Documents current behavior: contactless POS Walk-in (customer_id NULL)
# ---------------------------------------------------------------------------


async def test_contactless_pos_walkin_not_listed_under_customer(client: AsyncClient):
    headers, slug, product_id = await _setup(client)
    storefront = await _submit_storefront_order(client, slug, product_id, f"wi-{_uid()}@e.com")
    customer_id = storefront["customer_id"]

    await _open_shift(client, headers)
    walkin = await _create_pos_order(client, headers, product_id)
    assert walkin["customer_id"] is None  # contactless Walk-in -> no customer link

    r = await _get_customer_orders(client, headers, customer_id)
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()]
    assert ids == [storefront["id"]]
    assert walkin["id"] not in ids
