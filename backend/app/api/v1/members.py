"""Team member management endpoints."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from app.core.dependencies import (
    get_current_user,
    get_db_with_tenant,
    require_role,
)
from app.models.tenant_member import TenantMember
from app.models.user import User
from app.schemas.member import MemberInvite, MemberResponse

router = APIRouter()


@router.get("/", response_model=list[MemberResponse])
async def list_members(
    tenant_data: tuple = Depends(get_db_with_tenant),
    user: User = Depends(get_current_user),
):
    """List tenant members. Requires admin+ role."""
    db, tenant_id = tenant_data
    await require_role("admin", db, tenant_id, user)

    result = await db.execute(
        select(TenantMember)
        .where(TenantMember.status != "removed")
        .order_by(TenantMember.joined_at.asc().nulls_last())
    )
    members = result.scalars().all()

    response = []
    for m in members:
        # Load user info if available
        email = None
        full_name = None
        if m.user_id:
            user_result = await db.execute(select(User).where(User.id == m.user_id))
            member_user = user_result.scalar_one_or_none()
            if member_user:
                email = member_user.email
                full_name = member_user.full_name
        response.append(
            MemberResponse(
                id=m.id,
                user_id=m.user_id,
                email=email or m.invited_email,
                full_name=full_name,
                role=m.role,
                status=m.status,
                invited_at=m.invited_at,
                joined_at=m.joined_at,
            )
        )

    return response


@router.post("/invite", response_model=MemberResponse, status_code=201)
async def invite_member(
    body: MemberInvite,
    tenant_data: tuple = Depends(get_db_with_tenant),
    user: User = Depends(get_current_user),
):
    """Invite a user to the tenant by email. Requires admin+ role."""
    db, tenant_id = tenant_data
    await require_role("admin", db, tenant_id, user)

    # Check if already a member (by email match through user or invited_email)
    target_user_result = await db.execute(select(User).where(User.email == body.email))
    target_user = target_user_result.scalar_one_or_none()

    if target_user:
        existing = await db.execute(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant_id,
                TenantMember.user_id == target_user.id,
                TenantMember.status != "removed",
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="User is already a member")

    # Also check by invited_email
    existing_invite = await db.execute(
        select(TenantMember).where(
            TenantMember.tenant_id == tenant_id,
            TenantMember.invited_email == body.email,
            TenantMember.status == "invited",
        )
    )
    if existing_invite.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Invitation already pending")

    member = TenantMember(
        tenant_id=tenant_id,
        user_id=target_user.id if target_user else None,
        invited_email=body.email,
        role=body.role,
        status="invited",
        invited_at=datetime.now(UTC),
    )
    db.add(member)
    await db.flush()

    return MemberResponse(
        id=member.id,
        user_id=member.user_id,
        email=body.email,
        full_name=None,
        role=member.role,
        status=member.status,
        invited_at=member.invited_at,
        joined_at=None,
    )


@router.delete("/{member_id}", status_code=204)
async def remove_member(
    member_id: uuid.UUID,
    tenant_data: tuple = Depends(get_db_with_tenant),
    user: User = Depends(get_current_user),
):
    """Remove a member from the tenant. Requires admin+ role.

    Cannot remove the last owner.
    """
    db, tenant_id = tenant_data
    await require_role("admin", db, tenant_id, user)

    result = await db.execute(
        select(TenantMember).where(
            TenantMember.id == member_id,
            TenantMember.tenant_id == tenant_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    # Cannot remove the last owner
    if member.role == "owner":
        owner_count = await db.execute(
            select(func.count()).where(
                TenantMember.tenant_id == tenant_id,
                TenantMember.role == "owner",
                TenantMember.status == "active",
            )
        )
        if owner_count.scalar() <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last owner")

    member.status = "removed"
    await db.flush()
