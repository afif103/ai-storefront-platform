"""Product variant CRUD endpoint tests (M12.1 Step B)."""

import uuid

from httpx import AsyncClient

from tests.conftest import auth_headers


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _make_owner(client: AsyncClient) -> tuple[dict, str]:
    # Create a tenant with an owner; return (owner_headers, slug).
    uid = _uid()
    slug = f"pv-{uid}"
    headers = auth_headers(sub=f"pv-{uid}", email=f"pv-{uid}@test.com")
    headers["Content-Type"] = "application/json"
    r = await client.post(
        "/api/v1/tenants/", json={"name": f"PV {uid}", "slug": slug}, headers=headers
    )
    assert r.status_code == 201
    return headers, slug


async def _make_product(
    client: AsyncClient,
    headers: dict,
    *,
    sku: str | None = None,
    barcode: str | None = None,
) -> str:
    uid = _uid()
    payload: dict = {"name": f"Prod-{uid}", "price_amount": "5.000", "is_active": True}
    if sku is not None:
        payload["sku"] = sku
    if barcode is not None:
        payload["barcode"] = barcode
    r = await client.post("/api/v1/tenants/me/products", json=payload, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


async def _setup(client: AsyncClient) -> tuple[dict, str]:
    # Owner headers + a product id in the same tenant.
    headers, _slug = await _make_owner(client)
    product_id = await _make_product(client, headers)
    return headers, product_id


async def _invite(client: AsyncClient, owner_headers: dict, role: str) -> dict:
    # Invite + accept a member of the given role; return their headers.
    uid = _uid()
    email = f"{role}-{uid}@test.com"
    r = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": email, "role": role},
        headers=owner_headers,
    )
    assert r.status_code == 201
    headers = auth_headers(sub=f"{role}-{uid}", email=email)
    headers["Content-Type"] = "application/json"
    r = await client.post("/api/v1/auth/accept-invite", headers=headers)
    assert r.status_code == 200
    return headers


def _vurl(product_id: str) -> str:
    return f"/api/v1/tenants/me/products/{product_id}/variants"


async def test_create_variant_happy_path(client: AsyncClient):
    headers, product_id = await _setup(client)
    r = await client.post(
        _vurl(product_id),
        json={
            "name": "Large / Red",
            "size": "L",
            "color": "Red",
            "sku": "VAR-L-RED",
            "stock_qty": 7,
            "sort_order": 2,
        },
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["product_id"] == product_id
    assert data["name"] == "Large / Red"
    assert data["sku"] == "VAR-L-RED"
    assert data["stock_qty"] == 7
    assert data["is_active"] is True
    assert "tenant_id" not in data


async def test_list_variants_ordered_and_cashier_can_list(client: AsyncClient):
    owner, product_id = await _setup(client)
    for name, so in [("B", 2), ("A", 1), ("C", 3)]:
        r = await client.post(
            _vurl(product_id),
            json={"name": name, "sort_order": so},
            headers=owner,
        )
        assert r.status_code == 201

    cashier = await _invite(client, owner, "cashier")
    r = await client.get(_vurl(product_id), headers=cashier)
    assert r.status_code == 200
    items = r.json()["items"]
    assert [v["name"] for v in items] == ["A", "B", "C"]


async def test_get_variant_detail_as_member(client: AsyncClient):
    owner, product_id = await _setup(client)
    r = await client.post(_vurl(product_id), json={"name": "V1"}, headers=owner)
    variant_id = r.json()["id"]

    member = await _invite(client, owner, "member")
    r = await client.get(f"{_vurl(product_id)}/{variant_id}", headers=member)
    assert r.status_code == 200
    assert r.json()["id"] == variant_id


async def test_patch_variant_fields_and_is_active(client: AsyncClient):
    owner, product_id = await _setup(client)
    r = await client.post(
        _vurl(product_id),
        json={"name": "V1", "stock_qty": 5, "is_active": True},
        headers=owner,
    )
    variant_id = r.json()["id"]

    r = await client.patch(
        f"{_vurl(product_id)}/{variant_id}",
        json={"name": "V1 updated", "stock_qty": 9, "is_active": False},
        headers=owner,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "V1 updated"
    assert data["stock_qty"] == 9
    assert data["is_active"] is False


async def test_delete_variant_then_404(client: AsyncClient):
    owner, product_id = await _setup(client)
    r = await client.post(_vurl(product_id), json={"name": "V1"}, headers=owner)
    variant_id = r.json()["id"]

    r = await client.delete(f"{_vurl(product_id)}/{variant_id}", headers=owner)
    assert r.status_code == 204

    r = await client.get(f"{_vurl(product_id)}/{variant_id}", headers=owner)
    assert r.status_code == 404


async def test_duplicate_variant_sku_within_tenant_409(client: AsyncClient):
    owner, product_id = await _setup(client)
    r = await client.post(
        _vurl(product_id),
        json={"name": "V1", "sku": "DUP-SKU"},
        headers=owner,
    )
    assert r.status_code == 201
    r = await client.post(
        _vurl(product_id),
        json={"name": "V2", "sku": "DUP-SKU"},
        headers=owner,
    )
    assert r.status_code == 409


async def test_variant_sku_equal_to_product_sku_409(client: AsyncClient):
    headers, _slug = await _make_owner(client)
    product_id = await _make_product(client, headers, sku="SHARED-SKU")
    r = await client.post(
        _vurl(product_id),
        json={"name": "V1", "sku": "SHARED-SKU"},
        headers=headers,
    )
    assert r.status_code == 409


async def test_variant_barcode_equal_to_product_barcode_409(client: AsyncClient):
    headers, _slug = await _make_owner(client)
    product_id = await _make_product(client, headers, barcode="SHARED-BC")
    r = await client.post(
        _vurl(product_id),
        json={"name": "V1", "barcode": "SHARED-BC"},
        headers=headers,
    )
    assert r.status_code == 409


async def test_product_using_existing_variant_sku_409(client: AsyncClient):
    headers, _slug = await _make_owner(client)
    product_id = await _make_product(client, headers)
    r = await client.post(
        _vurl(product_id),
        json={"name": "V1", "sku": "VONLY-SKU"},
        headers=headers,
    )
    assert r.status_code == 201

    uid = _uid()
    r = await client.post(
        "/api/v1/tenants/me/products",
        json={"name": f"Prod2-{uid}", "price_amount": "1.000", "sku": "VONLY-SKU"},
        headers=headers,
    )
    assert r.status_code == 409

    r = await client.post(
        "/api/v1/tenants/me/products",
        json={"name": f"Prod3-{uid}", "price_amount": "1.000"},
        headers=headers,
    )
    assert r.status_code == 201
    p3 = r.json()["id"]
    r = await client.patch(
        f"/api/v1/tenants/me/products/{p3}",
        json={"sku": "VONLY-SKU"},
        headers=headers,
    )
    assert r.status_code == 409


async def test_member_cannot_write_cashier_can_list(client: AsyncClient):
    owner, product_id = await _setup(client)
    member = await _invite(client, owner, "member")
    cashier = await _invite(client, owner, "cashier")

    r = await client.post(_vurl(product_id), json={"name": "V1"}, headers=member)
    assert r.status_code == 403

    r = await client.post(_vurl(product_id), json={"name": "V1"}, headers=owner)
    variant_id = r.json()["id"]

    r = await client.patch(
        f"{_vurl(product_id)}/{variant_id}",
        json={"name": "X"},
        headers=member,
    )
    assert r.status_code == 403
    r = await client.delete(f"{_vurl(product_id)}/{variant_id}", headers=member)
    assert r.status_code == 403

    r = await client.get(_vurl(product_id), headers=cashier)
    assert r.status_code == 200


async def test_cross_tenant_variant_404(client: AsyncClient):
    owner_a, product_a = await _setup(client)
    r = await client.post(_vurl(product_a), json={"name": "V1"}, headers=owner_a)
    variant_id = r.json()["id"]

    owner_b, _slug_b = await _make_owner(client)
    r = await client.get(f"{_vurl(product_a)}/{variant_id}", headers=owner_b)
    assert r.status_code == 404
    r = await client.patch(
        f"{_vurl(product_a)}/{variant_id}",
        json={"name": "X"},
        headers=owner_b,
    )
    assert r.status_code == 404
    r = await client.delete(f"{_vurl(product_a)}/{variant_id}", headers=owner_b)
    assert r.status_code == 404


async def test_wrong_product_id_for_variant_404(client: AsyncClient):
    owner, product_id = await _setup(client)
    r = await client.post(_vurl(product_id), json={"name": "V1"}, headers=owner)
    variant_id = r.json()["id"]

    other_product = await _make_product(client, owner)
    r = await client.get(f"{_vurl(other_product)}/{variant_id}", headers=owner)
    assert r.status_code == 404


async def test_unknown_product_id_404(client: AsyncClient):
    owner, _product_id = await _setup(client)
    missing = str(uuid.uuid4())
    r = await client.get(_vurl(missing), headers=owner)
    assert r.status_code == 404
    r = await client.post(_vurl(missing), json={"name": "V1"}, headers=owner)
    assert r.status_code == 404


async def test_sku_barcode_whitespace_normalized_no_false_409(client: AsyncClient):
    owner, product_id = await _setup(client)
    r = await client.post(
        _vurl(product_id),
        json={"name": "V1", "sku": "   ", "barcode": ""},
        headers=owner,
    )
    assert r.status_code == 201
    assert r.json()["sku"] is None
    assert r.json()["barcode"] is None

    r = await client.post(
        _vurl(product_id),
        json={"name": "V2", "sku": "  ", "barcode": ""},
        headers=owner,
    )
    assert r.status_code == 201
    assert r.json()["sku"] is None


async def test_whitespace_only_name_422(client: AsyncClient):
    owner, product_id = await _setup(client)
    r = await client.post(_vurl(product_id), json={"name": "   "}, headers=owner)
    assert r.status_code == 422


async def test_patch_variant_to_existing_product_code_409(client: AsyncClient):
    headers, _slug = await _make_owner(client)
    product_id = await _make_product(
        client,
        headers,
        sku="PRODUCT-SKU",
        barcode="PRODUCT-BC",
    )
    r = await client.post(
        _vurl(product_id),
        json={"name": "V1", "sku": "VAR-SKU", "barcode": "VAR-BC"},
        headers=headers,
    )
    assert r.status_code == 201
    variant_id = r.json()["id"]

    r = await client.patch(
        f"{_vurl(product_id)}/{variant_id}",
        json={"sku": "PRODUCT-SKU"},
        headers=headers,
    )
    assert r.status_code == 409

    r = await client.patch(
        f"{_vurl(product_id)}/{variant_id}",
        json={"barcode": "PRODUCT-BC"},
        headers=headers,
    )
    assert r.status_code == 409
