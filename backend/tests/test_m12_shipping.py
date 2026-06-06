"""M12.5b backend tests: storefront shipping methods config + order delivery fee."""

from httpx import AsyncClient

from tests.m2_helpers import create_tenant_get_headers


def _method(mid: str, name: str, fee: str, active: bool = True) -> dict:
    return {"id": mid, "name": name, "fee": fee, "active": active}


def _ship(*methods: dict) -> dict:
    return {"shipping": {"methods": list(methods)}}


async def _setup_tenant_product(client: AsyncClient) -> tuple[dict, str, str]:
    """Create tenant + a priced product. Return (headers, slug, product_id)."""
    headers, slug = await create_tenant_get_headers(client, slug_prefix="m12ship")
    r = await client.post(
        "/api/v1/tenants/me/products",
        json={"name": "Ship Widget", "price_amount": "5.000", "is_active": True, "stock_qty": 100},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return headers, slug, r.json()["id"]


# ---------------------------------------------------------------------------
# 1. Storefront config shipping PUT/GET round-trip
# ---------------------------------------------------------------------------


async def test_put_get_shipping_config_roundtrip(client: AsyncClient):
    """Admin saves shipping methods; GET returns them; KWD 3-decimal fee preserved."""
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="ship-rt")
    body = _ship(
        _method("kwt", "Kuwait City", "1.500"),
        _method("oth", "Other Governorates", "2.250"),
    )
    r = await client.put("/api/v1/tenants/me/storefront", json=body, headers=headers)
    assert r.status_code == 200, r.text
    methods = r.json()["shipping"]["methods"]
    assert [m["id"] for m in methods] == ["kwt", "oth"]
    assert methods[0]["name"] == "Kuwait City"
    assert methods[0]["fee"] == "1.500"

    r = await client.get("/api/v1/tenants/me/storefront", headers=headers)
    assert r.status_code == 200
    saved = r.json()["shipping"]["methods"]
    assert saved[1]["fee"] == "2.250"
    assert saved[0]["active"] is True


# ---------------------------------------------------------------------------
# 2. Shipping config validation (422 at request-parse time)
# ---------------------------------------------------------------------------


async def test_shipping_config_rejects_empty_name(client: AsyncClient):
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="ship-name")
    body = _ship(_method("m1", "   ", "1.000"))
    r = await client.put("/api/v1/tenants/me/storefront", json=body, headers=headers)
    assert r.status_code == 422


async def test_shipping_config_rejects_negative_fee(client: AsyncClient):
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="ship-neg")
    body = _ship(_method("m1", "Zone", "-1.000"))
    r = await client.put("/api/v1/tenants/me/storefront", json=body, headers=headers)
    assert r.status_code == 422


async def test_shipping_config_rejects_excess_precision(client: AsyncClient):
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="ship-prec")
    body = _ship(_method("m1", "Zone", "1.5009"))
    r = await client.put("/api/v1/tenants/me/storefront", json=body, headers=headers)
    assert r.status_code == 422


async def test_shipping_config_rejects_duplicate_ids(client: AsyncClient):
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="ship-dup")
    body = _ship(_method("dup", "A", "1.000"), _method("dup", "B", "2.000"))
    r = await client.put("/api/v1/tenants/me/storefront", json=body, headers=headers)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# 3. Public storefront config exposure (active-only)
# ---------------------------------------------------------------------------


async def test_public_config_exposes_active_shipping_only(client: AsyncClient):
    headers, slug = await create_tenant_get_headers(client, slug_prefix="ship-pub")
    body = _ship(
        _method("act", "Active Zone", "1.000", active=True),
        _method("ina", "Inactive Zone", "9.000", active=False),
    )
    r = await client.put("/api/v1/tenants/me/storefront", json=body, headers=headers)
    assert r.status_code == 200, r.text

    r = await client.get(f"/api/v1/storefront/{slug}/config")
    assert r.status_code == 200
    methods = r.json()["shipping_methods"]
    assert methods is not None
    assert len(methods) == 1
    assert methods[0]["id"] == "act"
    assert methods[0]["fee"] == "1.000"
    assert "active" not in methods[0]


async def test_public_config_shipping_null_when_only_inactive(client: AsyncClient):
    headers, slug = await create_tenant_get_headers(client, slug_prefix="ship-ina")
    body = _ship(_method("ina", "Off", "1.000", active=False))
    r = await client.put("/api/v1/tenants/me/storefront", json=body, headers=headers)
    assert r.status_code == 200, r.text

    r = await client.get(f"/api/v1/storefront/{slug}/config")
    assert r.status_code == 200
    assert r.json()["shipping_methods"] is None


async def test_public_config_shipping_null_when_no_config(client: AsyncClient):
    _headers, slug = await create_tenant_get_headers(client, slug_prefix="ship-none")
    r = await client.get(f"/api/v1/storefront/{slug}/config")
    assert r.status_code == 200
    assert r.json()["shipping_methods"] is None


# ---------------------------------------------------------------------------
# 4. Order submit with a valid shipping method
# ---------------------------------------------------------------------------


async def test_order_with_shipping_method_applies_fee(client: AsyncClient):
    headers, slug, product_id = await _setup_tenant_product(client)
    body = _ship(_method("kwt", "Kuwait City", "1.500"))
    r = await client.put("/api/v1/tenants/me/storefront", json=body, headers=headers)
    assert r.status_code == 200, r.text

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Ahmad",
            "items": [{"catalog_item_id": product_id, "qty": 2}],
            "shipping_method_id": "kwt",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["total_amount"] == "11.500"  # 5.000 * 2 + 1.500 fee
    assert data["shipping_fee"] == "1.500"
    assert data["shipping_method"] == "Kuwait City"

    order_id = data["id"]
    r2 = await client.get(f"/api/v1/tenants/me/orders/{order_id}", headers=headers)
    assert r2.status_code == 200
    detail = r2.json()
    assert detail["shipping_fee"] == "1.500"
    assert detail["shipping_method"] == "Kuwait City"


# ---------------------------------------------------------------------------
# 5. Back-compat: no shipping_method_id
# ---------------------------------------------------------------------------


async def test_order_without_shipping_method_has_no_fee(client: AsyncClient):
    _headers, slug, product_id = await _setup_tenant_product(client)
    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Sara",
            "items": [{"catalog_item_id": product_id, "qty": 2}],
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["total_amount"] == "10.000"  # subtotal only, no fee
    assert data["shipping_fee"] is None
    assert data["shipping_method"] is None


# ---------------------------------------------------------------------------
# 6. Invalid / inactive / unconfigured shipping method -> 422
# ---------------------------------------------------------------------------


async def test_order_unknown_shipping_method_422(client: AsyncClient):
    headers, slug, product_id = await _setup_tenant_product(client)
    body = _ship(_method("kwt", "Kuwait City", "1.500"))
    r = await client.put("/api/v1/tenants/me/storefront", json=body, headers=headers)
    assert r.status_code == 200, r.text

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "X",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
            "shipping_method_id": "nope",
        },
    )
    assert r.status_code == 422


async def test_order_inactive_shipping_method_422(client: AsyncClient):
    headers, slug, product_id = await _setup_tenant_product(client)
    body = _ship(_method("off", "Disabled", "1.500", active=False))
    r = await client.put("/api/v1/tenants/me/storefront", json=body, headers=headers)
    assert r.status_code == 200, r.text

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "X",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
            "shipping_method_id": "off",
        },
    )
    assert r.status_code == 422


async def test_order_shipping_method_without_config_422(client: AsyncClient):
    _headers, slug, product_id = await _setup_tenant_product(client)
    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "X",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
            "shipping_method_id": "anything",
        },
    )
    assert r.status_code == 422
