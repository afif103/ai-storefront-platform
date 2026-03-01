"""Team member management tests."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


def _uid() -> str:
    return uuid.uuid4().hex[:8]


@pytest.mark.asyncio
async def test_invite_member_success(client: AsyncClient):
    """Invite a member to the tenant."""
    uid = _uid()
    owner_sub = f"inv-owner-{uid}"
    owner_email = f"inv-owner-{uid}@example.com"
    headers = auth_headers(sub=owner_sub, email=owner_email)
    headers["Content-Type"] = "application/json"

    await client.post(
        "/api/v1/tenants/",
        json={"name": f"Invite Test {uid}", "slug": f"inv-{uid}"},
        headers=headers,
    )

    # Invite a member
    invitee_email = f"invitee-{uid}@example.com"
    invite_resp = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": invitee_email, "role": "member"},
        headers=auth_headers(sub=owner_sub, email=owner_email),
    )
    assert invite_resp.status_code == 201
    data = invite_resp.json()
    assert data["email"] == invitee_email
    assert data["role"] == "member"
    assert data["status"] == "invited"


@pytest.mark.asyncio
async def test_invite_duplicate_rejected(client: AsyncClient):
    """Inviting the same email twice returns 409."""
    uid = _uid()
    owner_sub = f"dup-inv-{uid}"
    owner_email = f"dup-inv-{uid}@example.com"
    headers = auth_headers(sub=owner_sub, email=owner_email)
    headers["Content-Type"] = "application/json"

    await client.post(
        "/api/v1/tenants/",
        json={"name": f"Dup Invite {uid}", "slug": f"dup-inv-{uid}"},
        headers=headers,
    )

    h = auth_headers(sub=owner_sub, email=owner_email)
    invitee_email = f"dup-invitee-{uid}@example.com"

    # First invite
    resp1 = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": invitee_email, "role": "member"},
        headers=h,
    )
    assert resp1.status_code == 201

    # Second invite same email
    resp2 = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": invitee_email, "role": "admin"},
        headers=h,
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_list_members(client: AsyncClient):
    """List members returns the owner."""
    uid = _uid()
    owner_sub = f"list-owner-{uid}"
    owner_email = f"list-owner-{uid}@example.com"
    headers = auth_headers(sub=owner_sub, email=owner_email)
    headers["Content-Type"] = "application/json"

    await client.post(
        "/api/v1/tenants/",
        json={"name": f"List Test {uid}", "slug": f"list-{uid}"},
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
    uid = _uid()
    owner_sub = f"acc-owner-{uid}"
    owner_email = f"acc-owner-{uid}@example.com"
    invitee_email = f"acc-invitee-{uid}@example.com"
    invitee_sub = f"acc-invitee-{uid}"

    headers = auth_headers(sub=owner_sub, email=owner_email)
    headers["Content-Type"] = "application/json"

    await client.post(
        "/api/v1/tenants/",
        json={"name": f"Accept Test {uid}", "slug": f"acc-{uid}"},
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
