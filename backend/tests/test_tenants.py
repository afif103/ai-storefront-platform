"""Tenant creation and retrieval tests."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


def _uid() -> str:
    return uuid.uuid4().hex[:8]


@pytest.mark.asyncio
async def test_create_tenant_success(client: AsyncClient):
    """POST /tenants creates a tenant and owner membership."""
    uid = _uid()
    headers = auth_headers(sub=f"create-{uid}", email=f"creator-{uid}@example.com")
    headers["Content-Type"] = "application/json"

    slug = f"shop-{uid}"
    response = await client.post(
        "/api/v1/tenants/",
        json={"name": f"My Shop {uid}", "slug": slug},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == f"My Shop {uid}"
    assert data["slug"] == slug
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_tenant_duplicate_slug(client: AsyncClient):
    """POST /tenants with duplicate slug returns 409."""
    uid = _uid()
    headers = auth_headers(sub=f"dup-{uid}", email=f"dup-{uid}@example.com")
    headers["Content-Type"] = "application/json"

    slug = f"dup-slug-{uid}"

    # First creation succeeds
    response1 = await client.post(
        "/api/v1/tenants/",
        json={"name": "First", "slug": slug},
        headers=headers,
    )
    assert response1.status_code == 201

    # Second creation with same slug fails
    uid2 = _uid()
    headers2 = auth_headers(sub=f"dup2-{uid2}", email=f"dup2-{uid2}@example.com")
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
    uid = _uid()
    headers = auth_headers(sub=f"bad-{uid}", email=f"bad-{uid}@example.com")
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
    uid = _uid()
    sub = f"getme-{uid}"
    email = f"getme-{uid}@example.com"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    slug = f"me-{uid}"
    create_resp = await client.post(
        "/api/v1/tenants/",
        json={"name": f"My Tenant {uid}", "slug": slug},
        headers=headers,
    )
    assert create_resp.status_code == 201

    get_resp = await client.get(
        "/api/v1/tenants/me",
        headers=auth_headers(sub=sub, email=email),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["slug"] == slug


@pytest.mark.asyncio
async def test_get_tenant_me_no_membership(client: AsyncClient):
    """GET /tenants/me without a tenant returns 403."""
    uid = _uid()
    headers = auth_headers(sub=f"orphan-{uid}", email=f"orphan-{uid}@example.com")
    response = await client.get("/api/v1/tenants/me", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_tenant_unauthenticated(client: AsyncClient):
    """POST /tenants without auth returns 401."""
    response = await client.post(
        "/api/v1/tenants/",
        json={"name": "No Auth", "slug": f"noauth-{_uid()}"},
    )
    assert response.status_code == 401
