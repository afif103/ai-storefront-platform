"""Inventory service — single path for all stock movements."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.stock_movement import StockMovement


async def record_stock_movement(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    delta_qty: int,
    reason: str,
    note: str | None = None,
    order_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> StockMovement:
    """Insert a stock movement row and atomically update products.stock_qty.

    Both the INSERT and UPDATE happen in the caller's transaction —
    they commit or roll back together.
    """
    movement = StockMovement(
        tenant_id=tenant_id,
        product_id=product_id,
        delta_qty=delta_qty,
        reason=reason,
        note=note,
        order_id=order_id,
        actor_user_id=actor_user_id,
    )
    db.add(movement)

    # Atomic stock_qty update in the same transaction
    await db.execute(
        text(
            "UPDATE products SET stock_qty = stock_qty + :delta "
            "WHERE id = :product_id AND tenant_id = :tenant_id"
        ),
        {
            "delta": delta_qty,
            "product_id": str(product_id),
            "tenant_id": str(tenant_id),
        },
    )
    await db.flush()
    return movement


async def restore_stock_for_cancelled_order(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    order: object,
    actor_user_id: uuid.UUID | None = None,
) -> list[StockMovement]:
    """Restore stock for tracked items in a cancelled order.

    Idempotent: skips items that already have an ``order_cancel_restore``
    movement for this order.  A partial unique index on
    ``(order_id, product_id) WHERE reason = 'order_cancel_restore'``
    acts as a DB-level safety net.
    """
    movements: list[StockMovement] = []

    for item in order.items:  # type: ignore[attr-defined]
        product_id = uuid.UUID(item["catalog_item_id"])
        qty: int = item["qty"]

        # Only restore tracked-inventory products
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if product is None or not product.track_inventory:
            continue

        # Idempotency: skip if already restored for this order + product
        existing = await db.execute(
            select(StockMovement.id).where(
                StockMovement.order_id == order.id,  # type: ignore[attr-defined]
                StockMovement.product_id == product_id,
                StockMovement.reason == "order_cancel_restore",
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        movement = await record_stock_movement(
            db,
            tenant_id=tenant_id,
            product_id=product_id,
            delta_qty=qty,
            reason="order_cancel_restore",
            note=f"Restored from cancelled order {order.order_number}",  # type: ignore[attr-defined]
            order_id=order.id,  # type: ignore[attr-defined]
            actor_user_id=actor_user_id,
        )
        movements.append(movement)

    return movements
