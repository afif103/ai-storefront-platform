"""Tenant creation and retrieval tests."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_create_tenant_success(client: AsyncClient):
    """POST /tenants creates a tenant and owner membership."""
    headers = auth_headers(sub="create-tenant-sub", email="creator@example.com")
    headers["Content-Type"] = "application/json"

    response = await client.post(
        "/api/v1/tenants/",
        json={"name": "My Shop", "slug": "my-shop-test"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Shop"
    assert data["slug"] == "my-shop-test"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_tenant_duplicate_slug(client: AsyncClient):
    """POST /tenants with duplicate slug returns 409."""
    headers = auth_headers(sub="dup-slug-sub", email="dup@example.com")
    headers["Content-Type"] = "application/json"

    slug = "unique-slug-dup-test"

    # First creation succeeds
    response1 = await client.post(
        "/api/v1/tenants/",
        json={"name": "First", "slug": slug},
        headers=headers,
    )
    assert response1.status_code == 201

    # Second creation with same slug fails
    headers2 = auth_headers(sub="dup-slug-sub-2", email="dup2@example.com")
    headers2["Content-Type"] = "application/json"
    response2 = await client.post(
        "/api/v1/tenants/",
        json={"name": "Second", "slug": slug},
        headers=headers2,
    )
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_create_tenant_invalid_slug(client: AsyncClient):
    """POST /tenants with invalid slug returns 422."""
    headers = auth_headers(sub="bad-slug-sub", email="bad@example.com")
    headers["Content-Type"] = "application/json"

    response = await client.post(
        "/api/v1/tenants/",
        json={"name": "Bad Slug", "slug": "AB"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_tenant_me(client: AsyncClient):
    """GET /tenants/me returns the user's tenant after creation."""
    sub = "get-me-sub"
    email = "getme@example.com"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    # Create tenant first
    create_resp = await client.post(
        "/api/v1/tenants/",
        json={"name": "My Tenant", "slug": "my-tenant-me-test"},
        headers=headers,
    )
    assert create_resp.status_code == 201

    # Get tenant
    get_resp = await client.get(
        "/api/v1/tenants/me",
        headers=auth_headers(sub=sub, email=email),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["slug"] == "my-tenant-me-test"


@pytest.mark.asyncio
async def test_get_tenant_me_no_membership(client: AsyncClient):
    """GET /tenants/me without a tenant returns 403."""
    headers = auth_headers(sub="orphan-sub", email="orphan@example.com")
    response = await client.get("/api/v1/tenants/me", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_tenant_unauthenticated(client: AsyncClient):
    """POST /tenants without auth returns 401."""
    response = await client.post(
        "/api/v1/tenants/",
        json={"name": "No Auth", "slug": "no-auth-test"},
    )
    assert response.status_code == 401
