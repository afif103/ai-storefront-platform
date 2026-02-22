"""M2 integration tests: public visit capture endpoint."""

import pytest
from httpx import AsyncClient

from tests.m2_helpers import create_tenant_get_headers

pytestmark = pytest.mark.m2


async def test_capture_visit_success(client: AsyncClient):
    """POST /storefront/{slug}/visit creates a visit and returns visit_id."""
    _headers, slug = await create_tenant_get_headers(client, slug_prefix="visit-ok")

    body = {
        "session_id": "sess-abc-123",
        "landed_path": "/products",
        "referrer": "https://google.com",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "summer-sale",
    }
    resp = await client.post(f"/api/v1/storefront/{slug}/visit", json=body)
    assert resp.status_code == 201
    data = resp.json()
    assert "visit_id" in data


async def test_capture_visit_minimal_body(client: AsyncClient):
    """POST /storefront/{slug}/visit works with only required session_id."""
    _headers, slug = await create_tenant_get_headers(client, slug_prefix="visit-min")

    resp = await client.post(
        f"/api/v1/storefront/{slug}/visit",
        json={"session_id": "minimal-session"},
    )
    assert resp.status_code == 201
    assert "visit_id" in resp.json()


async def test_capture_visit_missing_session_id(client: AsyncClient):
    """POST /storefront/{slug}/visit without session_id returns 422."""
    _headers, slug = await create_tenant_get_headers(client, slug_prefix="visit-no")

    resp = await client.post(f"/api/v1/storefront/{slug}/visit", json={})
    assert resp.status_code == 422


async def test_capture_visit_bad_slug(client: AsyncClient):
    """POST /storefront/{slug}/visit with unknown slug returns 404."""
    resp = await client.post(
        "/api/v1/storefront/nonexistent-store-xyz/visit",
        json={"session_id": "test"},
    )
    assert resp.status_code == 404


async def test_capture_visit_no_auth_needed(client: AsyncClient):
    """Visit endpoint is public — no Authorization header required."""
    _headers, slug = await create_tenant_get_headers(client, slug_prefix="visit-pub")

    # Call without auth
    resp = await client.post(
        f"/api/v1/storefront/{slug}/visit",
        json={"session_id": "anon-visit"},
    )
    assert resp.status_code == 201
