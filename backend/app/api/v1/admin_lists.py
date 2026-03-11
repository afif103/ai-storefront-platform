"""Tenant-scoped list + export endpoints for orders, donations, pledges.

GET /tenants/me/orders
GET /tenants/me/donations
GET /tenants/me/pledges
GET /tenants/me/orders/export
GET /tenants/me/donations/export
GET /tenants/me/pledges/export

Role: member+ for lists, admin+ for exports.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
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
from app.services.csv_export import rows_to_csv_bytes

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

    stmt = select(Order).where(Order.tenant_id == tenant_id).order_by(Order.created_at.desc())
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

    stmt = (
        select(Donation)
        .where(Donation.tenant_id == tenant_id)
        .order_by(Donation.created_at.desc())
    )
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

    stmt = select(Pledge).where(Pledge.tenant_id == tenant_id).order_by(Pledge.created_at.desc())
    if status:
        stmt = stmt.where(Pledge.status == status.strip().lower())
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    return [PledgeListItem.model_validate(r) for r in result.scalars().all()]


# ---------------------------------------------------------------------------
# CSV exports (admin+)
# ---------------------------------------------------------------------------

MAX_EXPORT_ROWS = 10000


def _items_summary(items_json: list) -> str:
    """Flatten JSONB order items into a readable summary string."""
    parts = []
    for item in items_json:
        name = item.get("name", "?")
        qty = item.get("qty", 1)
        parts.append(f"{name} x{qty}")
    return "; ".join(parts)


def _csv_response(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/orders/export")
async def export_orders(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> Response:
    """Export orders as CSV. Admin+ role required."""
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    stmt = select(Order).where(Order.tenant_id == tenant_id).order_by(Order.created_at.desc())
    if start_date:
        stmt = stmt.where(Order.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Order.created_at < end_date)
    stmt = stmt.limit(MAX_EXPORT_ROWS)

    result = await db.execute(stmt)
    orders = result.scalars().all()

    headers = [
        "order_number",
        "status",
        "customer_name",
        "customer_phone",
        "customer_email",
        "items",
        "total_amount",
        "currency",
        "notes",
        "created_at",
    ]
    rows = [
        (
            o.order_number,
            o.status,
            o.customer_name,
            o.customer_phone,
            o.customer_email,
            _items_summary(o.items if isinstance(o.items, list) else []),
            o.total_amount,
            o.currency,
            o.notes,
            o.created_at,
        )
        for o in orders
    ]
    return _csv_response(rows_to_csv_bytes(headers, rows), "orders.csv")


@router.get("/donations/export")
async def export_donations(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> Response:
    """Export donations as CSV. Admin+ role required."""
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    stmt = (
        select(Donation)
        .where(Donation.tenant_id == tenant_id)
        .order_by(Donation.created_at.desc())
    )
    if start_date:
        stmt = stmt.where(Donation.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Donation.created_at < end_date)
    stmt = stmt.limit(MAX_EXPORT_ROWS)

    result = await db.execute(stmt)
    donations = result.scalars().all()

    headers = [
        "donation_number",
        "status",
        "donor_name",
        "donor_phone",
        "donor_email",
        "amount",
        "currency",
        "campaign",
        "receipt_requested",
        "notes",
        "created_at",
    ]
    rows = [
        (
            d.donation_number,
            d.status,
            d.donor_name,
            d.donor_phone,
            d.donor_email,
            d.amount,
            d.currency,
            d.campaign,
            d.receipt_requested,
            d.notes,
            d.created_at,
        )
        for d in donations
    ]
    return _csv_response(rows_to_csv_bytes(headers, rows), "donations.csv")


@router.get("/pledges/export")
async def export_pledges(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> Response:
    """Export pledges as CSV. Admin+ role required."""
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    stmt = select(Pledge).where(Pledge.tenant_id == tenant_id).order_by(Pledge.created_at.desc())
    if start_date:
        stmt = stmt.where(Pledge.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Pledge.created_at < end_date)
    stmt = stmt.limit(MAX_EXPORT_ROWS)

    result = await db.execute(stmt)
    pledges = result.scalars().all()

    headers = [
        "pledge_number",
        "status",
        "pledgor_name",
        "pledgor_phone",
        "pledgor_email",
        "amount",
        "currency",
        "target_date",
        "fulfilled_amount",
        "notes",
        "created_at",
    ]
    rows = [
        (
            p.pledge_number,
            p.status,
            p.pledgor_name,
            p.pledgor_phone,
            p.pledgor_email,
            p.amount,
            p.currency,
            p.target_date,
            p.fulfilled_amount,
            p.notes,
            p.created_at,
        )
        for p in pledges
    ]
    return _csv_response(rows_to_csv_bytes(headers, rows), "pledges.csv")
