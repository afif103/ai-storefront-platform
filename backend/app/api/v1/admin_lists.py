"""Tenant-scoped list endpoints for orders, donations, pledges.

GET /tenants/me/orders
GET /tenants/me/donations
GET /tenants/me/pledges

Role: member+. Limit/offset pagination (per CLAUDE.md MVP convention).
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_with_tenant, require_role
from app.models.donation import Donation
from app.models.order import Order
from app.models.pledge import Pledge
from app.models.user import User
from app.schemas.donation import DonationListItem
from app.schemas.order import OrderListItem
from app.schemas.pledge import PledgeListItem

router = APIRouter()

DEFAULT_LIMIT = 50


@router.get("/orders", response_model=list[OrderListItem])
async def list_orders(
    status: str | None = Query(None),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> list[OrderListItem]:
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    stmt = select(Order).order_by(Order.created_at.desc())
    if status:
        stmt = stmt.where(Order.status == status.strip().lower())
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    return [OrderListItem.model_validate(r) for r in result.scalars().all()]


@router.get("/donations", response_model=list[DonationListItem])
async def list_donations(
    status: str | None = Query(None),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> list[DonationListItem]:
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    stmt = select(Donation).order_by(Donation.created_at.desc())
    if status:
        stmt = stmt.where(Donation.status == status.strip().lower())
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    return [DonationListItem.model_validate(r) for r in result.scalars().all()]


@router.get("/pledges", response_model=list[PledgeListItem])
async def list_pledges(
    status: str | None = Query(None),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> list[PledgeListItem]:
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    stmt = select(Pledge).order_by(Pledge.created_at.desc())
    if status:
        stmt = stmt.where(Pledge.status == status.strip().lower())
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    return [PledgeListItem.model_validate(r) for r in result.scalars().all()]
