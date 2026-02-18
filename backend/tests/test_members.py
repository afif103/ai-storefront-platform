"""Team member management tests."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_invite_member_success(client: AsyncClient):
    """Invite a member to the tenant."""
    # Create tenant first
    owner_sub = "invite-owner-sub"
    owner_email = "invite-owner@example.com"
    headers = auth_headers(sub=owner_sub, email=owner_email)
    headers["Content-Type"] = "application/json"

    await client.post(
        "/api/v1/tenants/",
        json={"name": "Invite Test", "slug": "invite-test-tenant"},
        headers=headers,
    )

    # Invite a member
    invite_resp = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": "invitee@example.com", "role": "member"},
        headers=auth_headers(sub=owner_sub, email=owner_email),
    )
    assert invite_resp.status_code == 201
    data = invite_resp.json()
    assert data["email"] == "invitee@example.com"
    assert data["role"] == "member"
    assert data["status"] == "invited"


@pytest.mark.asyncio
async def test_invite_duplicate_rejected(client: AsyncClient):
    """Inviting the same email twice returns 409."""
    owner_sub = "dup-invite-owner"
    owner_email = "dup-invite-owner@example.com"
    headers = auth_headers(sub=owner_sub, email=owner_email)
    headers["Content-Type"] = "application/json"

    await client.post(
        "/api/v1/tenants/",
        json={"name": "Dup Invite Test", "slug": "dup-invite-test"},
        headers=headers,
    )

    h = auth_headers(sub=owner_sub, email=owner_email)

    # First invite
    resp1 = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": "dup-invitee@example.com", "role": "member"},
        headers=h,
    )
    assert resp1.status_code == 201

    # Second invite same email
    resp2 = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": "dup-invitee@example.com", "role": "admin"},
        headers=h,
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_list_members(client: AsyncClient):
    """List members returns the owner."""
    owner_sub = "list-members-owner"
    owner_email = "list-owner@example.com"
    headers = auth_headers(sub=owner_sub, email=owner_email)
    headers["Content-Type"] = "application/json"

    await client.post(
        "/api/v1/tenants/",
        json={"name": "List Test", "slug": "list-members-test"},
        headers=headers,
    )

    resp = await client.get(
        "/api/v1/tenants/me/members/",
        headers=auth_headers(sub=owner_sub, email=owner_email),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(m["role"] == "owner" for m in data)


@pytest.mark.asyncio
async def test_accept_invite(client: AsyncClient):
    """Accept invite transitions status from invited to active."""
    # Owner creates tenant
    owner_sub = "accept-owner-sub"
    owner_email = "accept-owner@example.com"
    invitee_email = "accept-invitee@example.com"
    invitee_sub = "accept-invitee-sub"

    headers = auth_headers(sub=owner_sub, email=owner_email)
    headers["Content-Type"] = "application/json"

    await client.post(
        "/api/v1/tenants/",
        json={"name": "Accept Test", "slug": "accept-invite-test"},
        headers=headers,
    )

    # Invite
    await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": invitee_email, "role": "member"},
        headers=auth_headers(sub=owner_sub, email=owner_email),
    )

    # Invitee accepts
    accept_resp = await client.post(
        "/api/v1/auth/accept-invite",
        headers=auth_headers(sub=invitee_sub, email=invitee_email),
    )
    assert accept_resp.status_code == 200
    data = accept_resp.json()
    assert len(data["accepted"]) == 1
    assert data["accepted"][0]["status"] == "active"
