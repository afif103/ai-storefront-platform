"""Tests for invited-row visibility under RLS via app.current_user_email.

Verifies that the third OR condition on the tenant_members SELECT policy
allows pending invitations (user_id IS NULL) to be visible when the
caller's email matches invited_email.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.tenant_member import TenantMember
from app.models.user import User

from .conftest import auth_headers


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _seed_invitation(
    db: AsyncSession,
    *,
    tenant_name: str,
    invited_email: str,
) -> tuple[Tenant, TenantMember]:
    """Create a tenant and a pending invitation (user_id=NULL)."""
    tenant = Tenant(name=tenant_name, slug=f"inv-{_uid()}")
    db.add(tenant)
    await db.flush()

    # INSERT requires app.current_tenant for RLS
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant.id)},
    )
    invitation = TenantMember(
        tenant_id=tenant.id,
        user_id=None,
        invited_email=invited_email.strip().lower(),
        role="member",
        status="invited",
    )
    db.add(invitation)
    await db.flush()

    # Clear tenant context so subsequent queries rely on user GUCs only
    await db.execute(text("RESET app.current_tenant"))

    return tenant, invitation


@pytest.mark.asyncio
async def test_invited_row_visible_via_email_guc(rls_db: AsyncSession):
    """Pending invitation is visible when app.current_user_email matches invited_email."""
    db = rls_db
    email = f"vis-{_uid()}@example.com"

    _, invitation = await _seed_invitation(db, tenant_name="Vis Test", invited_email=email)

    # Clear all user context
    await db.execute(text("RESET app.current_user_id"))
    await db.execute(text("RESET app.current_user_email"))
    await db.execute(text("RESET app.current_tenant"))

    # Without email GUC — invited row should be invisible
    result = await db.execute(
        select(TenantMember).where(TenantMember.id == invitation.id)
    )
    assert result.scalar_one_or_none() is None

    # Set email GUC — invited row should now be visible
    await db.execute(
        text("SELECT set_config('app.current_user_email', :email, true)"),
        {"email": email},
    )
    result = await db.execute(
        select(TenantMember).where(TenantMember.id == invitation.id)
    )
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.invited_email == email
    assert row.status == "invited"
    assert row.user_id is None


@pytest.mark.asyncio
async def test_invited_row_not_visible_to_wrong_email(rls_db: AsyncSession):
    """Pending invitation is NOT visible when email GUC does not match."""
    db = rls_db
    real_email = f"real-{_uid()}@example.com"
    wrong_email = f"wrong-{_uid()}@example.com"

    _, invitation = await _seed_invitation(
        db, tenant_name="Wrong Email Test", invited_email=real_email
    )

    await db.execute(text("RESET app.current_user_id"))
    await db.execute(text("RESET app.current_tenant"))
    await db.execute(
        text("SELECT set_config('app.current_user_email', :email, true)"),
        {"email": wrong_email},
    )

    result = await db.execute(
        select(TenantMember).where(TenantMember.id == invitation.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_invited_row_case_insensitive(rls_db: AsyncSession):
    """Email GUC matching works case-insensitively (both sides lowercased)."""
    db = rls_db
    email = f"CaSe-{_uid()}@Example.COM"
    normalized = email.strip().lower()

    _, invitation = await _seed_invitation(
        db, tenant_name="Case Test", invited_email=email
    )
    # _seed_invitation lowercases, so invited_email is stored normalized
    assert invitation.invited_email == normalized

    await db.execute(text("RESET app.current_user_id"))
    await db.execute(text("RESET app.current_tenant"))
    await db.execute(
        text("SELECT set_config('app.current_user_email', :email, true)"),
        {"email": normalized},
    )

    result = await db.execute(
        select(TenantMember).where(TenantMember.id == invitation.id)
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_bootstrap_pending_invitation_count_under_rls(rls_db: AsyncSession):
    """Simulates the bootstrap query: count pending invitations by email under RLS.

    Scenario: user exists but has no active memberships, one pending invitation.
    With only user GUCs set (no app.current_tenant), the pending invitation
    should be visible and countable.
    """
    db = rls_db
    uid = _uid()
    email = f"boot-{uid}@example.com"

    # Create the user (users table has no RLS)
    user = User(
        cognito_sub=f"boot-sub-{uid}",
        email=email,
        full_name="Bootstrap Test User",
    )
    db.add(user)
    await db.flush()

    # Create a pending invitation for this email
    tenant, _ = await _seed_invitation(
        db, tenant_name=f"Boot Tenant {uid}", invited_email=email
    )

    # Simulate bootstrap context: set user GUCs only, no tenant context
    await db.execute(text("RESET app.current_tenant"))
    await db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(user.id)},
    )
    await db.execute(
        text("SELECT set_config('app.current_user_email', :email, true)"),
        {"email": email},
    )

    # Query active memberships (should be empty)
    active_result = await db.execute(
        select(TenantMember).where(
            TenantMember.user_id == user.id,
            TenantMember.status == "active",
        )
    )
    active_memberships = active_result.scalars().all()
    assert len(active_memberships) == 0

    # Query pending invitations by email (should find 1)
    pending_result = await db.execute(
        select(TenantMember).where(
            TenantMember.invited_email == email,
            TenantMember.status == "invited",
        )
    )
    pending_invitations = pending_result.scalars().all()
    assert len(pending_invitations) == 1
    assert pending_invitations[0].tenant_id == tenant.id

    # Bootstrap logic: needs_onboarding should be false (has pending invite)
    needs_onboarding = len(active_memberships) == 0 and len(pending_invitations) == 0
    assert needs_onboarding is False


@pytest.mark.asyncio
async def test_accept_invite_under_rls(rls_client: AsyncClient):
    """accept_invite finds and flips invited rows under RLS enforcement."""
    uid = _uid()
    owner_sub = f"rls-owner-{uid}"
    owner_email = f"rls-owner-{uid}@example.com"
    invitee_sub = f"rls-invitee-{uid}"
    invitee_email = f"rls-invitee-{uid}@example.com"

    # Create tenant as owner
    resp = await rls_client.post(
        "/api/v1/tenants/",
        json={"name": f"RLS Accept {uid}", "slug": f"rls-acc-{uid}"},
        headers=auth_headers(sub=owner_sub, email=owner_email),
    )
    assert resp.status_code == 201

    # Owner invites the invitee
    resp = await rls_client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": invitee_email, "role": "member"},
        headers=auth_headers(sub=owner_sub, email=owner_email),
    )
    assert resp.status_code == 201

    # Invitee accepts — this is the key test: invited row must be visible under RLS
    resp = await rls_client.post(
        "/api/v1/auth/accept-invite",
        headers=auth_headers(sub=invitee_sub, email=invitee_email),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["accepted"]) == 1
    assert data["accepted"][0]["status"] == "active"
    assert data["accepted"][0]["role"] == "member"
