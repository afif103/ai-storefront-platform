"""M2 integration tests: GET /tenants/me/media list endpoint."""

import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient

from tests.m2_helpers import create_tenant_get_headers

pytestmark = pytest.mark.m2

MEDIA_URL = "/api/v1/tenants/me/media"
UPLOAD_URL = "/api/v1/tenants/me/media/upload-url"
PRODUCTS_URL = "/api/v1/tenants/me/products"


async def _create_product(client: AsyncClient, headers: dict) -> str:
    """Create a product via API and return its id."""
    resp = await client.post(
        PRODUCTS_URL,
        json={"name": f"Test Product {uuid.uuid4().hex[:8]}", "price_amount": "1.500"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_media(
    client: AsyncClient,
    headers: dict,
    *,
    file_name: str = "img.jpg",
    content_type: str = "image/jpeg",
    entity_type: str | None = None,
    entity_id: str | None = None,
    product_id: str | None = None,
) -> str:
    """Upload helper — returns media_id."""
    body: dict = {
        "file_name": file_name,
        "content_type": content_type,
        "size_bytes": 1024,
    }
    if entity_type and entity_id:
        body["entity_type"] = entity_type
        body["entity_id"] = entity_id
    if product_id:
        body["product_id"] = product_id

    resp = await client.post(UPLOAD_URL, json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["media_id"]


async def test_list_returns_own_tenant_media(rls_client: AsyncClient):
    """Tenant A sees only its own media assets."""
    headers_a, _ = await create_tenant_get_headers(rls_client, slug_prefix="ml-a")
    headers_b, _ = await create_tenant_get_headers(rls_client, slug_prefix="ml-b")

    media_a = await _create_media(rls_client, headers_a, file_name="a.png")
    media_b = await _create_media(rls_client, headers_b, file_name="b.png")

    resp = await rls_client.get(MEDIA_URL, headers=headers_a)
    assert resp.status_code == 200
    items = resp.json()
    ids = [item["id"] for item in items]
    assert media_a in ids
    assert media_b not in ids
    for item in items:
        assert "id" in item
        assert "s3_key" in item
        assert "created_at" in item


async def test_list_product_id_filter(rls_client: AsyncClient):
    """product_id filter returns only matching media."""
    headers, _ = await create_tenant_get_headers(rls_client, slug_prefix="ml-pf")

    product_id = await _create_product(rls_client, headers)
    other_product_id = await _create_product(rls_client, headers)

    m1 = await _create_media(rls_client, headers, file_name="p1.jpg", product_id=product_id)
    m2 = await _create_media(rls_client, headers, file_name="p2.jpg", product_id=product_id)
    m3 = await _create_media(
        rls_client, headers, file_name="other.jpg", product_id=other_product_id
    )

    resp = await rls_client.get(f"{MEDIA_URL}?product_id={product_id}", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    ids = [item["id"] for item in items]
    assert m1 in ids
    assert m2 in ids
    assert m3 not in ids


async def test_list_entity_type_and_id_filter(rls_client: AsyncClient):
    """entity_type + entity_id filter returns only matching media."""
    headers, _ = await create_tenant_get_headers(rls_client, slug_prefix="ml-ef")

    entity_id = str(uuid.uuid4())

    m1 = await _create_media(
        rls_client,
        headers,
        file_name="ent1.jpg",
        entity_type="product",
        entity_id=entity_id,
    )
    m2 = await _create_media(rls_client, headers, file_name="no-ent.jpg")

    resp = await rls_client.get(
        f"{MEDIA_URL}?entity_type=product&entity_id={entity_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    items = resp.json()
    ids = [item["id"] for item in items]
    assert m1 in ids
    assert m2 not in ids


async def test_list_ordering_and_limit(rls_client: AsyncClient):
    """Results are ordered by created_at DESC and limit/offset works."""
    headers, _ = await create_tenant_get_headers(rls_client, slug_prefix="ml-ol")

    ids = []
    for i in range(3):
        mid = await _create_media(rls_client, headers, file_name=f"ord-{i}.jpg")
        ids.append(mid)

    # Default order: most recent first
    resp = await rls_client.get(MEDIA_URL, headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    # Filter to only our created items (RLS scopes to tenant)
    our_items = [item for item in items if item["id"] in ids]
    assert len(our_items) == 3
    # Assert created_at is sorted DESC
    times = [
        datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")) for item in our_items
    ]
    assert all(times[i] >= times[i + 1] for i in range(len(times) - 1))

    # Limit
    resp2 = await rls_client.get(f"{MEDIA_URL}?limit=1", headers=headers)
    assert resp2.status_code == 200
    assert len(resp2.json()) == 1

    # Offset
    resp3 = await rls_client.get(f"{MEDIA_URL}?limit=1&offset=1", headers=headers)
    assert resp3.status_code == 200
    items3 = resp3.json()
    assert len(items3) == 1
    assert items3[0]["id"] != resp2.json()[0]["id"]


async def test_list_unauthenticated(client: AsyncClient):
    """GET /tenants/me/media without auth returns 401."""
    resp = await client.get(MEDIA_URL)
    assert resp.status_code == 401


async def test_list_empty(rls_client: AsyncClient):
    """GET /tenants/me/media with no media returns empty list."""
    headers, _ = await create_tenant_get_headers(rls_client, slug_prefix="ml-em")

    resp = await rls_client.get(MEDIA_URL, headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []
