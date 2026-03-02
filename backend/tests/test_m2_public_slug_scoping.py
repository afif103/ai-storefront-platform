"""M2 integration tests: public storefront slug scoping (categories, products).

Note: The test DB engine connects as postgres (superuser), which bypasses RLS.
Public endpoints rely on SET LOCAL + RLS for tenant scoping, so in these tests
we cannot assert on empty lists or exact counts. Instead we verify:
- Items we created are present in the response
- Items from other tenants are NOT present (cross-tenant isolation)
- Filters work (active-only, category_id)
"""

import pytest
from httpx import AsyncClient

from tests.m2_helpers import create_tenant_get_headers

pytestmark = pytest.mark.m2


async def test_public_categories_success(client: AsyncClient):
    """GET /storefront/{slug}/categories returns 200 with paginated response."""
    _headers, slug = await create_tenant_get_headers(client, slug_prefix="pub-cat-s")

    resp = await client.get(f"/api/v1/storefront/{slug}/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "has_more" in data


async def test_public_categories_includes_created(client: AsyncClient):
    """Categories created via dashboard appear in public endpoint."""
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pub-cat-i")

    # Create active category
    cat_resp = await client.post(
        "/api/v1/tenants/me/categories",
        json={"name": "Visible Category PCI"},
        headers=headers,
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    resp = await client.get(f"/api/v1/storefront/{slug}/categories?limit=100")
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert cat_id in ids


async def test_public_categories_excludes_inactive(client: AsyncClient):
    """Inactive categories do not appear in public endpoint."""
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pub-cat-x")

    # Create inactive category
    cat_resp = await client.post(
        "/api/v1/tenants/me/categories",
        json={"name": "Hidden Category PCX", "is_active": False},
        headers=headers,
    )
    assert cat_resp.status_code == 201
    hidden_id = cat_resp.json()["id"]

    resp = await client.get(f"/api/v1/storefront/{slug}/categories")
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert hidden_id not in ids


async def test_public_products_success(client: AsyncClient):
    """GET /storefront/{slug}/products returns 200."""
    _headers, slug = await create_tenant_get_headers(client, slug_prefix="pub-prod-s")

    resp = await client.get(f"/api/v1/storefront/{slug}/products")
    assert resp.status_code == 200
    assert "items" in resp.json()


async def test_public_products_with_currency_fallback(client: AsyncClient):
    """Public products include effective_currency from tenant default."""
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pub-prod-c")

    # Create a product without explicit currency.
    # sort_order=-1 ensures it appears first in the results — the superuser
    # test connection bypasses RLS, so products from ALL tenants accumulate
    # across runs and can exceed the page limit.
    prod_resp = await client.post(
        "/api/v1/tenants/me/products",
        json={"name": "Widget PPC", "price_amount": "1.500", "sort_order": -1},
        headers=headers,
    )
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]

    resp = await client.get(f"/api/v1/storefront/{slug}/products?limit=100")
    assert resp.status_code == 200
    items = resp.json()["items"]
    product = next((p for p in items if p["id"] == prod_id), None)
    assert product is not None, f"product {prod_id} not in {len(items)} items"
    # Should fall back to tenant default currency (KWD)
    assert product["effective_currency"] == "KWD"


async def test_public_products_excludes_inactive(client: AsyncClient):
    """Inactive products do not appear in public endpoint."""
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pub-prod-x")

    prod_resp = await client.post(
        "/api/v1/tenants/me/products",
        json={"name": "Hidden PPX", "price_amount": "3.000", "is_active": False},
        headers=headers,
    )
    assert prod_resp.status_code == 201
    hidden_id = prod_resp.json()["id"]

    resp = await client.get(f"/api/v1/storefront/{slug}/products")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["items"]]
    assert hidden_id not in ids


async def test_public_products_filter_by_category(client: AsyncClient):
    """Public products endpoint supports category_id filter."""
    headers, slug = await create_tenant_get_headers(client, slug_prefix="pub-filt")

    # Create category
    cat_resp = await client.post(
        "/api/v1/tenants/me/categories",
        json={"name": "Electronics PF"},
        headers=headers,
    )
    cat_id = cat_resp.json()["id"]

    # Product in category
    p1 = await client.post(
        "/api/v1/tenants/me/products",
        json={"name": "Phone PF", "price_amount": "99.000", "category_id": cat_id},
        headers=headers,
    )
    phone_id = p1.json()["id"]

    # Product without category
    p2 = await client.post(
        "/api/v1/tenants/me/products",
        json={"name": "Misc PF", "price_amount": "10.000"},
        headers=headers,
    )
    misc_id = p2.json()["id"]

    # Filter by category
    resp = await client.get(f"/api/v1/storefront/{slug}/products?category_id={cat_id}")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["items"]]
    assert phone_id in ids
    assert misc_id not in ids


async def test_public_slug_not_found(client: AsyncClient):
    """GET /storefront/{bad-slug}/categories returns 404."""
    resp = await client.get("/api/v1/storefront/no-such-store-xyz/categories")
    assert resp.status_code == 404


@pytest.mark.skip(
    reason="RLS isolation requires app_user connection; superuser bypasses RLS. "
    "Covered by tests/test_rls_isolation.py with rls_db fixture."
)
async def test_cross_tenant_isolation(client: AsyncClient):
    """Tenant A's products are not visible on Tenant B's public storefront.

    This test requires RLS enforcement, which only works when connected as
    app_user. The test client uses postgres (superuser), so RLS is bypassed.
    """
    headers_a, slug_a = await create_tenant_get_headers(client, slug_prefix="iso-a")
    _headers_b, slug_b = await create_tenant_get_headers(client, slug_prefix="iso-b")

    # Create product on tenant A with unique name
    p = await client.post(
        "/api/v1/tenants/me/products",
        json={"name": "A-Only-Product-ISO", "price_amount": "25.000"},
        headers=headers_a,
    )
    a_product_id = p.json()["id"]

    # Tenant A's storefront has the product
    resp_a = await client.get(f"/api/v1/storefront/{slug_a}/products")
    assert resp_a.status_code == 200
    ids_a = [p["id"] for p in resp_a.json()["items"]]
    assert a_product_id in ids_a

    # Tenant B's storefront does NOT have it
    resp_b = await client.get(f"/api/v1/storefront/{slug_b}/products")
    assert resp_b.status_code == 200
    ids_b = [p["id"] for p in resp_b.json()["items"]]
    assert a_product_id not in ids_b
