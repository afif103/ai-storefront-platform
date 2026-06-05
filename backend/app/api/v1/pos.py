"""POS (point-of-sale) endpoints — tenant-authenticated."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_with_tenant, require_role
from app.models.audit_event import AuditEvent
from app.models.order import Order
from app.models.pos_shift import PosShift
from app.models.storefront_config import StorefrontConfig
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.order import OrderCreateResponse, OrderListItem
from app.schemas.payment import DEFAULT_POS_PAYMENT_METHODS, PosPaymentMethodsResponse
from app.schemas.pos import PosOrderCreateRequest
from app.schemas.pos_shift import (
    PosCurrentShiftResponse,
    PosShiftCloseRequest,
    PosShiftOpenRequest,
    PosShiftResponse,
)
from app.services.inventory import restore_stock_for_cancelled_order
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


async def _get_open_shift(db: AsyncSession, tenant_id: uuid.UUID) -> PosShift | None:
    result = await db.execute(
        select(PosShift).where(
            PosShift.tenant_id == tenant_id,
            PosShift.status == "open",
        )
    )
    return result.scalar_one_or_none()


async def _compute_cash_sales(
    db: AsyncSession, tenant_id: uuid.UUID, shift_id: uuid.UUID
) -> Decimal:
    """Sum cash (non-cancelled) POS sales rung up under a shift."""
    result = await db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.tenant_id == tenant_id,
            Order.source == "pos",
            Order.shift_id == shift_id,
            Order.payment_method == "cash",
            Order.status != "cancelled",
        )
    )
    return Decimal(result.scalar_one())


def _shift_response(shift: PosShift, cash_sales: Decimal) -> PosShiftResponse:
    expected = shift.starting_cash + cash_sales
    variance = shift.counted_cash - expected if shift.counted_cash is not None else None
    return PosShiftResponse(
        id=shift.id,
        status=shift.status,
        starting_cash=shift.starting_cash,
        cash_sales=cash_sales,
        expected_cash=expected,
        counted_cash=shift.counted_cash,
        variance=variance,
        opened_at=shift.opened_at,
        opened_by=shift.opened_by,
        closed_at=shift.closed_at,
        closed_by=shift.closed_by,
        notes=shift.notes,
    )


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


@router.get("/payment-methods", response_model=PosPaymentMethodsResponse)
async def get_pos_payment_methods(
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> PosPaymentMethodsResponse:
    """Return enabled POS payment methods for the tenant (cashier-readable).

    Falls back to DEFAULT_POS_PAYMENT_METHODS when no config exists or no POS
    methods are configured.
    """
    db, tenant_id = db_tenant
    await require_role("cashier", db, tenant_id, user)

    result = await db.execute(
        select(StorefrontConfig).where(StorefrontConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()

    methods: list[str] = []
    if config and config.payment_methods:
        methods = config.payment_methods.get("pos") or []

    if not methods:
        methods = list(DEFAULT_POS_PAYMENT_METHODS)

    return PosPaymentMethodsResponse(payment_methods=methods)


@router.get("/shifts/current", response_model=PosCurrentShiftResponse)
async def get_current_shift(
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> PosCurrentShiftResponse:
    """Return the tenant's open POS shift with live cash summary, or null."""
    db, tenant_id = db_tenant
    await require_role("cashier", db, tenant_id, user)

    shift = await _get_open_shift(db, tenant_id)
    if shift is None:
        return PosCurrentShiftResponse(shift=None)

    cash_sales = await _compute_cash_sales(db, tenant_id, shift.id)
    return PosCurrentShiftResponse(shift=_shift_response(shift, cash_sales))


@router.post("/shifts/open", response_model=PosShiftResponse, status_code=201)
async def open_shift(
    body: PosShiftOpenRequest,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> PosShiftResponse:
    """Open a POS shift with a starting cash float. 409 if one is already open."""
    db, tenant_id = db_tenant
    await require_role("cashier", db, tenant_id, user)

    if await _get_open_shift(db, tenant_id) is not None:
        raise HTTPException(status_code=409, detail="A POS shift is already open")

    shift = PosShift(
        tenant_id=tenant_id,
        status="open",
        starting_cash=body.starting_cash,
        opened_by=user.id,
    )
    db.add(shift)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A POS shift is already open") from exc

    await db.refresh(shift)
    await db.commit()
    return _shift_response(shift, Decimal("0"))


@router.post("/shifts/close", response_model=PosShiftResponse)
async def close_shift(
    body: PosShiftCloseRequest,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> PosShiftResponse:
    """Close the open POS shift, snapshotting cash sales. 409 if none open."""
    db, tenant_id = db_tenant
    await require_role("cashier", db, tenant_id, user)

    shift = await _get_open_shift(db, tenant_id)
    if shift is None:
        raise HTTPException(status_code=409, detail="No open POS shift to close")

    cash_sales = await _compute_cash_sales(db, tenant_id, shift.id)
    shift.status = "closed"
    shift.counted_cash = body.counted_cash
    shift.closing_cash_sales = cash_sales
    shift.closed_by = user.id
    shift.closed_at = datetime.now(UTC)
    shift.notes = body.notes
    await db.commit()
    return _shift_response(shift, cash_sales)


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

    shift = await _get_open_shift(db, tenant_id)
    if shift is None:
        raise HTTPException(status_code=409, detail="Open a POS shift before creating a sale")

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
        actor_user_id=user.id,
        payment_method=body.payment_method,
    )
    order.shift_id = shift.id
    await db.flush()

    await db.commit()

    return OrderCreateResponse.model_validate(order)


@router.patch("/orders/{order_id}/cancel", response_model=OrderCreateResponse)
async def cancel_pos_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> OrderCreateResponse:
    """Cancel a fulfilled POS order and restore stock.

    Only fulfilled -> cancelled is allowed. This rule is local to the POS
    endpoint and does not touch ORDER_TRANSITIONS.
    Returns 404 for missing, cross-tenant, or non-POS orders.
    """
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

    if order.status == "cancelled":
        raise HTTPException(status_code=409, detail="Order already cancelled")
    if order.status != "fulfilled":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel order in status '{order.status}'",
        )

    order.status = "cancelled"
    order.updated_at = datetime.now(UTC)
    await db.flush()

    await restore_stock_for_cancelled_order(
        db, tenant_id=tenant_id, order=order, actor_user_id=user.id
    )

    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=user.id,
            entity_type="order",
            entity_id=order.id,
            action="status_transition",
            from_status="fulfilled",
            to_status="cancelled",
        )
    )

    await db.commit()

    return OrderCreateResponse.model_validate(order)
