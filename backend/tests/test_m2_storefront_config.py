"""M2 integration tests: storefront config API (authenticated + public)."""

import pytest
from httpx import AsyncClient

from tests.m2_helpers import create_tenant_get_headers

pytestmark = pytest.mark.m2


async def test_get_config_returns_null_when_not_set(client: AsyncClient):
    """GET /tenants/me/storefront returns null before any config is created."""
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="cfg-null")
    resp = await client.get("/api/v1/tenants/me/storefront", headers=headers)
    assert resp.status_code == 200
    assert resp.json() is None


async def test_put_config_creates_and_returns(client: AsyncClient):
    """PUT /tenants/me/storefront upserts config."""
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="cfg-put")
    body = {
        "hero_text": "Welcome!",
        "primary_color": "#112233",
        "secondary_color": "#AABBCC",
    }
    resp = await client.put("/api/v1/tenants/me/storefront", json=body, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["hero_text"] == "Welcome!"
    assert data["primary_color"] == "#112233"
    assert data["secondary_color"] == "#AABBCC"
    assert "id" in data
    assert "tenant_id" not in data


async def test_put_config_patch_semantics(client: AsyncClient):
    """PUT with partial fields only updates those fields."""
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="cfg-patch")

    # Create initial config
    await client.put(
        "/api/v1/tenants/me/storefront",
        json={"hero_text": "Original", "primary_color": "#000000"},
        headers=headers,
    )

    # Partial update — only hero_text
    resp = await client.put(
        "/api/v1/tenants/me/storefront",
        json={"hero_text": "Updated"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["hero_text"] == "Updated"
    assert data["primary_color"] == "#000000"  # unchanged


async def test_put_config_rejects_invalid_color(client: AsyncClient):
    """PUT with invalid hex color returns 422."""
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="cfg-color")
    resp = await client.put(
        "/api/v1/tenants/me/storefront",
        json={"primary_color": "red"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_public_config_endpoint(client: AsyncClient):
    """GET /storefront/{slug}/config returns branding without tenant_id."""
    headers, slug = await create_tenant_get_headers(client, slug_prefix="cfg-pub")

    # Set config
    await client.put(
        "/api/v1/tenants/me/storefront",
        json={"hero_text": "Public Hero", "primary_color": "#FF0000"},
        headers=headers,
    )

    # Public (no auth) request
    resp = await client.get(f"/api/v1/storefront/{slug}/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["hero_text"] == "Public Hero"
    assert data["primary_color"] == "#FF0000"
    assert "tenant_id" not in data
    assert "id" not in data


async def test_public_config_returns_defaults_when_missing(client: AsyncClient):
    """GET /storefront/{slug}/config returns all-null defaults when no config."""
    headers, slug = await create_tenant_get_headers(client, slug_prefix="cfg-def")

    resp = await client.get(f"/api/v1/storefront/{slug}/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["hero_text"] is None
    assert data["primary_color"] is None
    assert data["secondary_color"] is None
    assert data["logo_url"] is None


async def test_public_config_404_for_bad_slug(client: AsyncClient):
    """GET /storefront/{slug}/config returns 404 for unknown slug."""
    resp = await client.get("/api/v1/storefront/nonexistent-slug-xyz/config")
    assert resp.status_code == 404
