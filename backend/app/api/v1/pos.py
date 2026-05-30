"""POS (point-of-sale) endpoints — tenant-authenticated."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_with_tenant, require_role
from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.order import OrderCreateResponse, OrderListItem
from app.schemas.pos import PosOrderCreateRequest
from app.services.order_create import create_order

router = APIRouter()

DEFAULT_PAGE_SIZE = 20


def _encode_cursor(order: Order) -> str:
    return f"{order.created_at.isoformat()}|{order.id}"


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        dt_str, id_str = cursor.split("|", 1)
        return datetime.fromisoformat(dt_str), uuid.UUID(id_str)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


@router.get("/orders", response_model=PaginatedResponse[OrderListItem])
async def list_pos_orders(
    cursor: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> PaginatedResponse[OrderListItem]:
    """List POS orders (source='pos') for the tenant, newest first."""
    db, tenant_id = db_tenant
    await require_role("cashier", db, tenant_id, user)

    stmt = (
        select(Order)
        .where(Order.tenant_id == tenant_id, Order.source == "pos")
        .order_by(Order.created_at.desc(), Order.id.desc())
    )
    if cursor:
        cursor_dt, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(
            tuple_(Order.created_at, Order.id) < tuple_(cursor_dt, cursor_id),
        )
    stmt = stmt.limit(limit + 1)

    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]

    return PaginatedResponse(
        items=[OrderListItem.model_validate(o) for o in items],
        next_cursor=_encode_cursor(items[-1]) if has_more and items else None,
        has_more=has_more,
    )


@router.get("/orders/{order_id}", response_model=OrderCreateResponse)
async def get_pos_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> OrderCreateResponse:
    """Get a single POS order by ID. Returns 404 for non-POS or missing orders."""
    db, tenant_id = db_tenant
    await require_role("cashier", db, tenant_id, user)

    result = await db.execute(
        select(Order).where(
            Order.id == order_id,
            Order.tenant_id == tenant_id,
            Order.source == "pos",
        )
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return OrderCreateResponse.model_validate(order)


@router.post("/orders", response_model=OrderCreateResponse, status_code=201)
async def create_pos_order(
    body: PosOrderCreateRequest,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> OrderCreateResponse:
    """Create a POS order.

    Validates products, decrements stock atomically, and creates an order
    with source='pos' and status='fulfilled'.
    """
    db, tenant_id = db_tenant
    await require_role("cashier", db, tenant_id, user)

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one()

    order = await create_order(
        db,
        tenant_id=tenant_id,
        tenant_currency=tenant.default_currency or "KWD",
        items=body.items,
        customer_name=body.customer_name or "Walk-in",
        source="pos",
        status="fulfilled",
    )

    await db.commit()

    return OrderCreateResponse.model_validate(order)
