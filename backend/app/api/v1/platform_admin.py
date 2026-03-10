"""Platform admin endpoints — cross-tenant management.

GET  /admin/tenants           — list all tenants
POST /admin/tenants/{id}/suspend    — suspend a tenant
POST /admin/tenants/{id}/reactivate — reactivate a tenant

All endpoints require is_platform_admin=true on the authenticated user.
These endpoints use get_db() (no tenant context by default).

RLS strategy:
- app.current_user_id is SET LOCAL to the admin's user ID at the start of
  each endpoint. This activates the tenant_members_platform_admin_select
  RLS policy (SELECT-only, checks users.is_platform_admin).
- Suspend/reactivate also SET LOCAL app.current_tenant to the target tenant
  before writing audit events, so the audit_events INSERT check passes.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_platform_admin
from app.models.audit_event import AuditEvent
from app.models.donation import Donation
from app.models.order import Order
from app.models.pledge import Pledge
from app.models.tenant import Tenant
from app.models.tenant_member import TenantMember
from app.models.user import User
from app.schemas.platform_admin import AdminTenantActionResponse, AdminTenantListItem

router = APIRouter()

DEFAULT_LIMIT = 50


@router.get("/tenants", response_model=list[AdminTenantListItem])
async def list_tenants(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminTenantListItem]:
    """List all tenants with member count. Platform admin only."""
    # Set user context so platform admin RLS policy on tenant_members activates
    await db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(admin.id)},
    )

    member_count_sub = (
        select(func.count(TenantMember.id))
        .where(
            TenantMember.tenant_id == Tenant.id,
            TenantMember.status == "active",
        )
        .correlate(Tenant)
        .scalar_subquery()
        .label("member_count")
    )

    order_count_sub = (
        select(func.count(Order.id))
        .where(Order.tenant_id == Tenant.id)
        .correlate(Tenant)
        .scalar_subquery()
        .label("order_count")
    )

    donation_count_sub = (
        select(func.count(Donation.id))
        .where(Donation.tenant_id == Tenant.id)
        .correlate(Tenant)
        .scalar_subquery()
        .label("donation_count")
    )

    pledge_count_sub = (
        select(func.count(Pledge.id))
        .where(Pledge.tenant_id == Tenant.id)
        .correlate(Tenant)
        .scalar_subquery()
        .label("pledge_count")
    )

    last_order = (
        select(func.max(Order.created_at))
        .where(Order.tenant_id == Tenant.id)
        .correlate(Tenant)
        .scalar_subquery()
    )
    last_donation = (
        select(func.max(Donation.created_at))
        .where(Donation.tenant_id == Tenant.id)
        .correlate(Tenant)
        .scalar_subquery()
    )
    last_pledge = (
        select(func.max(Pledge.created_at))
        .where(Pledge.tenant_id == Tenant.id)
        .correlate(Tenant)
        .scalar_subquery()
    )
    last_activity_sub = func.greatest(
        last_order, last_donation, last_pledge
    ).label("last_activity_at")

    stmt = (
        select(
            Tenant,
            member_count_sub,
            order_count_sub,
            donation_count_sub,
            pledge_count_sub,
            last_activity_sub,
        )
        .order_by(Tenant.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        AdminTenantListItem(
            id=t.id,
            name=t.name,
            slug=t.slug,
            is_active=t.is_active,
            created_at=t.created_at,
            member_count=mc,
            order_count=oc,
            donation_count=dc,
            pledge_count=pc,
            last_activity_at=la,
        )
        for t, mc, oc, dc, pc, la in rows
    ]


@router.post("/tenants/{tenant_id}/suspend", response_model=AdminTenantActionResponse)
async def suspend_tenant(
    tenant_id: uuid.UUID,
    admin: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTenantActionResponse:
    """Suspend a tenant. Platform admin only."""
    # Set user context for any RLS-protected reads in this transaction
    await db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(admin.id)},
    )

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if not tenant.is_active:
        raise HTTPException(status_code=409, detail="Tenant is already suspended")

    tenant.is_active = False

    # Set tenant context so audit_events RLS INSERT check passes
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant.id)},
    )

    audit = AuditEvent(
        tenant_id=tenant.id,
        actor_user_id=admin.id,
        entity_type="tenant",
        entity_id=tenant.id,
        action="tenant.suspended",
    )
    db.add(audit)

    await db.flush()
    return AdminTenantActionResponse.model_validate(tenant)


@router.post("/tenants/{tenant_id}/reactivate", response_model=AdminTenantActionResponse)
async def reactivate_tenant(
    tenant_id: uuid.UUID,
    admin: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTenantActionResponse:
    """Reactivate a suspended tenant. Platform admin only."""
    # Set user context for any RLS-protected reads in this transaction
    await db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(admin.id)},
    )

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if tenant.is_active:
        raise HTTPException(status_code=409, detail="Tenant is already active")

    tenant.is_active = True

    # Set tenant context so audit_events RLS INSERT check passes
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant.id)},
    )

    audit = AuditEvent(
        tenant_id=tenant.id,
        actor_user_id=admin.id,
        entity_type="tenant",
        entity_id=tenant.id,
        action="tenant.reactivated",
    )
    db.add(audit)

    await db.flush()
    return AdminTenantActionResponse.model_validate(tenant)
