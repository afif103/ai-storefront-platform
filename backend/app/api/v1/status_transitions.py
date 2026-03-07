"""Admin status transition endpoints for orders, donations, pledges.

PATCH /tenants/me/orders/{id}/status
PATCH /tenants/me/donations/{id}/status
PATCH /tenants/me/pledges/{id}/status

Enforces strict transition rules per docs/M3_remaining.md.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_with_tenant, require_role
from app.models.audit_event import AuditEvent
from app.models.donation import Donation
from app.models.order import Order
from app.models.pledge import Pledge
from app.models.user import User
from app.schemas.status_transition import (
    DonationStatusResponse,
    OrderStatusResponse,
    PledgeStatusResponse,
    StatusTransitionRequest,
)
from app.services.inventory import restore_stock_for_cancelled_order

router = APIRouter()

# ---------------------------------------------------------------------------
# Allowed transitions (from docs/M3_remaining.md)
# ---------------------------------------------------------------------------

ORDER_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["confirmed", "cancelled"],
    "confirmed": ["fulfilled", "cancelled"],
    "fulfilled": [],
    "cancelled": [],
}

DONATION_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["received", "cancelled"],
    "received": ["receipted", "cancelled"],
    "receipted": [],
    "cancelled": [],
}

PLEDGE_TRANSITIONS: dict[str, list[str]] = {
    "pledged": ["partially_fulfilled", "lapsed"],
    "partially_fulfilled": ["fulfilled", "lapsed"],
    "fulfilled": [],
    "lapsed": [],
}


def _validate_transition(
    current: str,
    requested: str,
    transitions: dict[str, list[str]],
    entity_type: str,
) -> None:
    """Raise 422 if the transition is not allowed."""
    allowed = transitions.get(current, [])
    if requested not in allowed:
        raise HTTPException(
            status_code=422,
            detail={
                "message": (f"Cannot transition {entity_type} from '{current}' to '{requested}'"),
                "allowed": allowed,
            },
        )


async def _log_audit(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    from_status: str,
    to_status: str,
) -> None:
    """Insert an audit_events row for a status transition."""
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action="status_transition",
        from_status=from_status,
        to_status=to_status,
    )
    db.add(event)
    await db.flush()


# ---------------------------------------------------------------------------
# PATCH /tenants/me/orders/{order_id}/status
# ---------------------------------------------------------------------------


@router.patch("/orders/{order_id}/status", response_model=OrderStatusResponse)
async def transition_order_status(
    order_id: uuid.UUID,
    body: StatusTransitionRequest,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> OrderStatusResponse:
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    requested = body.status.strip().lower()
    old_status = order.status
    _validate_transition(old_status, requested, ORDER_TRANSITIONS, "order")

    order.status = requested
    order.updated_at = datetime.now(UTC)
    await db.flush()
    await _log_audit(db, tenant_id, user.id, "order", order_id, old_status, requested)

    # Restore stock on true transition into cancelled
    if requested == "cancelled" and old_status != "cancelled":
        await restore_stock_for_cancelled_order(
            db, tenant_id=tenant_id, order=order, actor_user_id=user.id
        )

    await db.refresh(order)

    return OrderStatusResponse.model_validate(order)


# ---------------------------------------------------------------------------
# PATCH /tenants/me/donations/{donation_id}/status
# ---------------------------------------------------------------------------


@router.patch("/donations/{donation_id}/status", response_model=DonationStatusResponse)
async def transition_donation_status(
    donation_id: uuid.UUID,
    body: StatusTransitionRequest,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> DonationStatusResponse:
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    result = await db.execute(select(Donation).where(Donation.id == donation_id))
    donation = result.scalar_one_or_none()
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found")

    requested = body.status.strip().lower()
    old_status = donation.status
    _validate_transition(old_status, requested, DONATION_TRANSITIONS, "donation")

    donation.status = requested
    donation.updated_at = datetime.now(UTC)
    await db.flush()
    await _log_audit(db, tenant_id, user.id, "donation", donation_id, old_status, requested)
    await db.refresh(donation)

    return DonationStatusResponse.model_validate(donation)


# ---------------------------------------------------------------------------
# PATCH /tenants/me/pledges/{pledge_id}/status
# ---------------------------------------------------------------------------


@router.patch("/pledges/{pledge_id}/status", response_model=PledgeStatusResponse)
async def transition_pledge_status(
    pledge_id: uuid.UUID,
    body: StatusTransitionRequest,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> PledgeStatusResponse:
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    result = await db.execute(select(Pledge).where(Pledge.id == pledge_id))
    pledge = result.scalar_one_or_none()
    if pledge is None:
        raise HTTPException(status_code=404, detail="Pledge not found")

    requested = body.status.strip().lower()
    old_status = pledge.status
    _validate_transition(old_status, requested, PLEDGE_TRANSITIONS, "pledge")

    pledge.status = requested
    pledge.updated_at = datetime.now(UTC)
    await db.flush()
    await _log_audit(db, tenant_id, user.id, "pledge", pledge_id, old_status, requested)
    await db.refresh(pledge)

    return PledgeStatusResponse.model_validate(pledge)
