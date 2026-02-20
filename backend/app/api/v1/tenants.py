"""Tenant management endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_db_with_tenant
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.models.tenant_member import TenantMember
from app.models.user import User
from app.schemas.tenant import TenantCreate, TenantResponse

router = APIRouter()


@router.post("/", response_model=TenantResponse, status_code=201)
async def create_tenant(
    body: TenantCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new tenant. The authenticated user becomes the owner.

    This is a pre-tenant endpoint — uses get_current_user (not get_db_with_tenant)
    because the user may not have any tenant yet.
    """
    # Get default free plan
    result = await db.execute(select(Plan).where(Plan.name == "Free").limit(1))
    free_plan = result.scalar_one_or_none()

    # Create tenant
    tenant = Tenant(
        name=body.name,
        slug=body.slug,
        plan_id=free_plan.id if free_plan else None,
        default_currency=body.default_currency or "KWD",
    )
    db.add(tenant)

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Slug already taken") from exc

    # Set tenant context for the tenant_members INSERT (RLS requires it)
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant.id)},
    )

    # Create owner membership
    membership = TenantMember(
        tenant_id=tenant.id,
        user_id=user.id,
        role="owner",
        status="active",
        joined_at=datetime.now(UTC),
    )
    db.add(membership)
    await db.flush()

    return tenant


@router.get("/me", response_model=TenantResponse)
async def get_current_tenant(
    tenant_data: tuple = Depends(get_db_with_tenant),
):
    """Get the current tenant (resolved from JWT)."""
    db, tenant_id = tenant_data
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant
