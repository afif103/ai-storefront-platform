"""Auth endpoint tests (POST /auth/refresh hardening)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_refresh_rejects_missing_cookie(client: AsyncClient):
    """POST /auth/refresh without cookie returns 401."""
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401
    assert "refresh token" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_rejects_wrong_content_type(client: AsyncClient):
    """POST /auth/refresh with wrong Content-Type returns 415."""
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Content-Type": "text/plain"},
        cookies={"refresh_token": "some-token"},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_origin(client: AsyncClient):
    """POST /auth/refresh with invalid Origin in non-dev mode."""
    # In dev mode, non-allowlisted origins are rejected when Origin is set
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={
            "Content-Type": "application/json",
            "Origin": "https://evil.com",
        },
        cookies={"refresh_token": "some-token"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_refresh_succeeds_with_mock(client: AsyncClient):
    """POST /auth/refresh with valid cookie returns new access token."""
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Content-Type": "application/json"},
        cookies={"refresh_token": "mock-refresh-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert len(data["access_token"]) > 0
