"""POS (point-of-sale) endpoints — tenant-authenticated."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_with_tenant
from app.models.tenant import Tenant
from app.schemas.order import OrderCreateResponse
from app.schemas.pos import PosOrderCreateRequest
from app.services.order_create import create_order

router = APIRouter()


@router.post("/orders", response_model=OrderCreateResponse, status_code=201)
async def create_pos_order(
    body: PosOrderCreateRequest,
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> OrderCreateResponse:
    """Create a POS order.

    Validates products, decrements stock atomically, and creates an order
    with source='pos' and status='fulfilled'.
    """
    db, tenant_id = db_tenant

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
