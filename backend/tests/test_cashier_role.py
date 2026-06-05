"""Cashier role permission boundary tests."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.cashier


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _setup_with_cashier(
    client: AsyncClient,
) -> tuple[dict, dict, str]:
    """Create tenant + product as owner, invite + accept cashier.

    Returns (owner_headers, cashier_headers, product_id).
    """
    uid = _uid()

    # Owner creates tenant
    owner_sub = f"owner-{uid}"
    owner_email = f"owner-{uid}@test.com"
    owner_headers = auth_headers(sub=owner_sub, email=owner_email)
    owner_headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"CashierTest {uid}", "slug": f"cashier-{uid}"},
        headers=owner_headers,
    )
    assert r.status_code == 201

    # Owner creates a product
    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"TestProduct-{uid}",
            "price_amount": "3.000",
            "is_active": True,
            "track_inventory": True,
            "stock_qty": 20,
        },
        headers=owner_headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]

    # Owner invites cashier
    cashier_email = f"cashier-{uid}@test.com"
    r = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": cashier_email, "role": "cashier"},
        headers=owner_headers,
    )
    assert r.status_code == 201

    # Cashier accepts invite
    cashier_sub = f"cashier-{uid}"
    cashier_headers = auth_headers(sub=cashier_sub, email=cashier_email)
    cashier_headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/auth/accept-invite",
        headers=cashier_headers,
    )
    assert r.status_code == 200

    # Hard gating: open a POS shift so POS sales can be created in these tests.
    r = await client.post(
        "/api/v1/tenants/me/pos/shifts/open",
        json={"starting_cash": "0.000"},
        headers=owner_headers,
    )
    assert r.status_code == 201

    return owner_headers, cashier_headers, product_id


# ---- ALLOW tests ----


async def test_cashier_can_create_pos_order(client: AsyncClient):
    # Cashier can create a POS order.
    _, cashier_headers, product_id = await _setup_with_cashier(client)

    r = await client.post(
        "/api/v1/tenants/me/pos/orders",
        json={"items": [{"catalog_item_id": product_id, "qty": 1}]},
        headers=cashier_headers,
    )
    assert r.status_code == 201
    assert r.json()["source"] == "pos"
    assert r.json()["status"] == "fulfilled"


async def test_cashier_can_list_products(client: AsyncClient):
    # Cashier can read the product catalog.
    _, cashier_headers, _ = await _setup_with_cashier(client)

    r = await client.get(
        "/api/v1/tenants/me/products",
        headers=cashier_headers,
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1


async def test_role_update_to_cashier(client: AsyncClient):
    # Owner can update an existing member's role to cashier.
    uid = _uid()

    # Owner creates tenant
    owner_sub = f"owner-{uid}"
    owner_email = f"owner-{uid}@test.com"
    owner_headers = auth_headers(sub=owner_sub, email=owner_email)
    owner_headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"RoleUpdate {uid}", "slug": f"roleupd-{uid}"},
        headers=owner_headers,
    )
    assert r.status_code == 201

    # Owner invites a regular member
    member_email = f"member-{uid}@test.com"
    r = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": member_email, "role": "member"},
        headers=owner_headers,
    )
    assert r.status_code == 201

    # Member accepts invite
    member_sub = f"member-{uid}"
    member_headers = auth_headers(sub=member_sub, email=member_email)
    member_headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/auth/accept-invite",
        headers=member_headers,
    )
    assert r.status_code == 200

    # Find the member's membership ID
    r = await client.get("/api/v1/tenants/me/members/", headers=owner_headers)
    assert r.status_code == 200
    members = r.json()
    member_entry = next(m for m in members if m.get("email") == member_email)
    member_id = member_entry["id"]

    # Owner updates member role to cashier
    r = await client.patch(
        f"/api/v1/tenants/me/members/{member_id}",
        json={"role": "cashier"},
        headers=owner_headers,
    )
    assert r.status_code == 200
    assert r.json()["role"] == "cashier"


# ---- DENY tests ----


async def test_cashier_cannot_get_product_detail(client: AsyncClient):
    # Cashier is denied single product detail (only list is lowered).
    _, cashier_headers, product_id = await _setup_with_cashier(client)

    r = await client.get(
        f"/api/v1/tenants/me/products/{product_id}",
        headers=cashier_headers,
    )
    assert r.status_code == 403


async def test_cashier_cannot_create_product(client: AsyncClient):
    # Cashier is denied product creation.
    _, cashier_headers, _ = await _setup_with_cashier(client)

    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": "Forbidden",
            "price_amount": "1.000",
            "is_active": True,
        },
        headers=cashier_headers,
    )
    assert r.status_code == 403


async def test_cashier_cannot_list_orders(client: AsyncClient):
    # Cashier is denied storefront order list.
    _, cashier_headers, _ = await _setup_with_cashier(client)

    r = await client.get(
        "/api/v1/tenants/me/orders",
        headers=cashier_headers,
    )
    assert r.status_code == 403


async def test_cashier_cannot_list_categories(client: AsyncClient):
    # Cashier is denied category access.
    _, cashier_headers, _ = await _setup_with_cashier(client)

    r = await client.get(
        "/api/v1/tenants/me/categories",
        headers=cashier_headers,
    )
    assert r.status_code == 403


async def test_cashier_cannot_manage_members(client: AsyncClient):
    # Cashier is denied team management.
    _, cashier_headers, _ = await _setup_with_cashier(client)

    r = await client.get(
        "/api/v1/tenants/me/members/",
        headers=cashier_headers,
    )
    assert r.status_code == 403


async def test_owner_still_has_full_access(client: AsyncClient):
    # Owner retains full access after cashier is added.
    owner_headers, _, product_id = await _setup_with_cashier(client)

    # Owner can list products
    r = await client.get("/api/v1/tenants/me/products", headers=owner_headers)
    assert r.status_code == 200

    # Owner can create POS order
    r = await client.post(
        "/api/v1/tenants/me/pos/orders",
        json={"items": [{"catalog_item_id": product_id, "qty": 1}]},
        headers=owner_headers,
    )
    assert r.status_code == 201

    # Owner can list orders
    r = await client.get("/api/v1/tenants/me/orders", headers=owner_headers)
    assert r.status_code == 200

    # Owner can list members
    r = await client.get("/api/v1/tenants/me/members/", headers=owner_headers)
    assert r.status_code == 200
