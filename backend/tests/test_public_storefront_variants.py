"""Public storefront variant exposure tests (M12.2 P3 Phase A).

The test DB connects as superuser (RLS bypassed), so these assert on
presence/absence of items we created rather than exact counts. Products are
created with sort_order=-1 so they land on the first page under accumulation.
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.m2_helpers import create_tenant_get_headers

pytestmark = pytest.mark.m2


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _make_product(client: AsyncClient, headers: dict, **fields: object) -> str:
    payload: dict = {
        "name": f"Prod-{_uid()}",
        "price_amount": "5.000",
        "is_active": True,
        "sort_order": -1,
    }
    payload.update(fields)
    r = await client.post("/api/v1/tenants/me/products", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _make_variant(
    client: AsyncClient, headers: dict, product_id: str, **fields: object
) -> str:
    payload: dict = {"name": f"Var-{_uid()}"}
    payload.update(fields)
    r = await client.post(
        f"/api/v1/tenants/me/products/{product_id}/variants",
        json=payload,
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _get_public_product(client: AsyncClient, slug: str, product_id: str) -> dict | None:
    r = await client.get(f"/api/v1/storefront/{slug}/products?limit=100")
    assert r.status_code == 200
    return next((p for p in r.json()["items"] if p["id"] == product_id), None)


async def test_public_products_include_active_variants(client: AsyncClient):
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pv-pub-inc")
    product_id = await _make_product(client, headers)
    variant_id = await _make_variant(
        client, headers, product_id, name="Large / Red", size="L", color="Red", stock_qty=3
    )

    product = await _get_public_product(client, slug, product_id)
    assert product is not None
    v = next(v for v in product["variants"] if v["id"] == variant_id)
    assert v["name"] == "Large / Red"
    assert v["size"] == "L"
    assert v["color"] == "Red"
    assert v["in_stock"] is True


async def test_inactive_variants_hidden(client: AsyncClient):
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pv-pub-inact")
    product_id = await _make_product(client, headers)
    active_id = await _make_variant(client, headers, product_id, name="Active", stock_qty=1)
    inactive_id = await _make_variant(
        client, headers, product_id, name="Inactive", stock_qty=1, is_active=False
    )

    product = await _get_public_product(client, slug, product_id)
    assert product is not None
    ids = [v["id"] for v in product["variants"]]
    assert active_id in ids
    assert inactive_id not in ids


async def test_variants_ordered_by_sort_order(client: AsyncClient):
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pv-pub-ord")
    product_id = await _make_product(client, headers)
    for name, so in [("B", 2), ("A", 1), ("C", 3)]:
        await _make_variant(client, headers, product_id, name=name, sort_order=so, stock_qty=1)

    product = await _get_public_product(client, slug, product_id)
    assert product is not None
    assert [v["name"] for v in product["variants"]] == ["A", "B", "C"]


async def test_no_sensitive_variant_fields_leaked(client: AsyncClient):
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pv-pub-safe")
    product_id = await _make_product(client, headers)
    variant_id = await _make_variant(
        client,
        headers,
        product_id,
        name="Safe",
        sku="VAR-SKU-1",
        barcode="VAR-BC-1",
        stock_qty=4,
    )

    product = await _get_public_product(client, slug, product_id)
    assert product is not None
    v = next(v for v in product["variants"] if v["id"] == variant_id)
    assert set(v.keys()) == {"id", "name", "size", "color", "price_amount", "in_stock"}
    for leaked in ("sku", "barcode", "stock_qty", "is_active"):
        assert leaked not in v


async def test_in_stock_true_for_untracked_parent(client: AsyncClient):
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pv-pub-untr")
    product_id = await _make_product(client, headers, track_inventory=False)
    variant_id = await _make_variant(client, headers, product_id, name="NoTrack")

    product = await _get_public_product(client, slug, product_id)
    assert product is not None
    v = next(v for v in product["variants"] if v["id"] == variant_id)
    assert v["in_stock"] is True


async def test_in_stock_false_for_tracked_zero_or_null_stock(client: AsyncClient):
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pv-pub-zero")
    product_id = await _make_product(client, headers, track_inventory=True, stock_qty=0)
    zero_id = await _make_variant(client, headers, product_id, name="Zero", stock_qty=0)
    null_id = await _make_variant(client, headers, product_id, name="Null")

    product = await _get_public_product(client, slug, product_id)
    assert product is not None
    by_id = {v["id"]: v for v in product["variants"]}
    assert by_id[zero_id]["in_stock"] is False
    assert by_id[null_id]["in_stock"] is False


async def test_variant_price_override_and_null(client: AsyncClient):
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pv-pub-price")
    product_id = await _make_product(client, headers)
    override_id = await _make_variant(
        client, headers, product_id, name="Override", price_amount="9.500", stock_qty=1
    )
    inherit_id = await _make_variant(client, headers, product_id, name="Inherit", stock_qty=1)

    product = await _get_public_product(client, slug, product_id)
    assert product is not None
    by_id = {v["id"]: v for v in product["variants"]}
    assert by_id[override_id]["price_amount"] == "9.500"
    assert by_id[inherit_id]["price_amount"] is None


async def test_cross_tenant_variants_not_leaked(client: AsyncClient):
    headers_a, slug_a = await create_tenant_get_headers(client, slug_prefix="pv-iso-a")
    _headers_b, slug_b = await create_tenant_get_headers(client, slug_prefix="pv-iso-b")
    product_a = await _make_product(client, headers_a)
    variant_a = await _make_variant(client, headers_a, product_a, name="A-Var", stock_qty=1)

    prod_on_a = await _get_public_product(client, slug_a, product_a)
    assert prod_on_a is not None
    ids_on_a = [v["id"] for v in prod_on_a["variants"]]
    assert variant_a in ids_on_a

    prod_on_b = await _get_public_product(client, slug_b, product_a)
    if prod_on_b is not None:
        ids_on_b = [v["id"] for v in prod_on_b["variants"]]
        assert variant_a not in ids_on_b


async def test_product_without_variants_returns_empty_list(client: AsyncClient):
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pv-pub-none")
    product_id = await _make_product(client, headers)

    product = await _get_public_product(client, slug, product_id)
    assert product is not None
    assert product["variants"] == []


async def test_public_order_with_variant_succeeds(client: AsyncClient):
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pv-pub-order")
    product_id = await _make_product(client, headers, track_inventory=True, stock_qty=10)
    variant_id = await _make_variant(client, headers, product_id, name="OrderVar", stock_qty=5)

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Buyer",
            "items": [{"catalog_item_id": product_id, "variant_id": variant_id, "qty": 1}],
        },
    )
    assert r.status_code == 201, r.text
