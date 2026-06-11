"""Auth endpoint tests (POST /auth/refresh hardening + mock identity continuity)."""

import uuid

import pytest
from httpx import AsyncClient
from jose import jwt


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _mock_login(client: AsyncClient, email: str) -> tuple[str, str]:
    """Mock email/password login. Returns (access_token, refresh_cookie_value)."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "anything"},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    access_token = response.json()["access_token"]
    refresh_cookie = response.cookies.get("refresh_token")
    assert refresh_cookie is not None
    return access_token, refresh_cookie


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
    """POST /auth/refresh with a valid mock_login-shaped cookie returns a new token.

    The old lax cookie value 'mock-refresh-token' is now rejected (it does not
    encode an identity) — see test_refresh_rejects_invalid_mock_cookies.
    """
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Content-Type": "application/json"},
        cookies={"refresh_token": "mock-refresh-mock-0123456789abcdef"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert len(data["access_token"]) > 0


# ---------------------------------------------------------------------------
# Mock identity continuity (refresh must keep the logged-in user's identity)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_login_sets_identity_refresh_cookie(client: AsyncClient):
    """Mock login's refresh cookie is 'mock-refresh-<sub>' for the issued sub."""
    access_token, refresh_cookie = await _mock_login(client, f"auth-{_uid()}@test.com")
    sub = jwt.get_unverified_claims(access_token)["sub"]
    assert sub.startswith("mock-")
    assert refresh_cookie == f"mock-refresh-{sub}"


@pytest.mark.asyncio
async def test_mock_refresh_preserves_identity(client: AsyncClient):
    """Refreshing mints a token for the SAME sub, and bootstrap stays the same user."""
    email = f"auth-{_uid()}@test.com"
    access_token, _refresh_cookie = await _mock_login(client, email)
    sub = jwt.get_unverified_claims(access_token)["sub"]

    # The login response stored the cookie in the client jar; refresh uses it.
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    new_token = response.json()["access_token"]
    assert jwt.get_unverified_claims(new_token)["sub"] == sub

    # End-to-end: the refreshed token resolves to the SAME user (no auto-provision,
    # no users_email_key collision, no identity switch).
    response = await client.post(
        "/api/v1/auth/bootstrap",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["user"]["email"] == email


@pytest.mark.asyncio
async def test_mock_refresh_does_not_mint_hardcoded_identity(client: AsyncClient):
    """The refreshed token never carries the old hardcoded stub identity."""
    await _mock_login(client, f"auth-{_uid()}@test.com")
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    claims = jwt.get_unverified_claims(response.json()["access_token"])
    assert claims["sub"] != "mock-user-sub"
    assert claims.get("email") != "dev@example.com"


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_mock_cookies(client: AsyncClient):
    """Garbage / legacy / identity-less mock cookies return 401 (clean re-login)."""
    bad_values = (
        "garbage",
        "mock-refresh-token-rotated",  # legacy rotated value
        "mock-refresh-",  # empty sub
        "mock-refresh-other-sub",  # sub outside the mock- namespace
    )
    for bad in bad_values:
        response = await client.post(
            "/api/v1/auth/refresh",
            headers={"Content-Type": "application/json"},
            cookies={"refresh_token": bad},
        )
        assert response.status_code == 401, f"{bad!r} -> {response.status_code}"
        assert "invalid or expired" in response.json()["detail"].lower()
