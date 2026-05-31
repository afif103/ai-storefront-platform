"""Shared order creation logic used by storefront and POS endpoints."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.product import Product
from app.schemas.order import OrderItemRequest
from app.services.inventory import record_stock_movement
from app.services.numbering import get_next_order_number


async def create_order(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    tenant_currency: str,
    items: list[OrderItemRequest],
    customer_name: str,
    customer_phone: str | None = None,
    customer_email: str | None = None,
    source: str,
    status: str,
    payment_notes: str | None = None,
    notes: str | None = None,
    visit_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> Order:
    """Validate products, decrement stock, and create an Order row.

    The caller is responsible for commit timing, UTM events, and notifications.
    On validation or stock failure, raises HTTPException (422 or 409).

    Duplicate product IDs in *items* are processed as separate line items
    (each decrements stock independently).  This matches existing storefront
    behaviour — callers that want dedup should handle it at the schema layer.
    """
    if not items:
        raise HTTPException(status_code=422, detail="Order must have at least one item")

    # Fetch all requested products in one query
    product_ids = [item.catalog_item_id for item in items]
    result = await db.execute(
        select(Product).where(
            Product.id.in_(product_ids),
            Product.tenant_id == tenant_id,
            Product.is_active.is_(True),
        )
    )
    products_by_id = {p.id: p for p in result.scalars().all()}

    # Validate all items exist, are active, and have a price
    for item in items:
        if item.catalog_item_id not in products_by_id:
            raise HTTPException(
                status_code=422,
                detail=f"Product {item.catalog_item_id} not found or inactive",
            )
        product = products_by_id[item.catalog_item_id]
        if product.price_amount is None:
            raise HTTPException(
                status_code=422,
                detail=f"Product {item.catalog_item_id} has no price",
            )

    # Build JSONB snapshot and compute total
    order_currency = tenant_currency
    items_jsonb: list[dict] = []
    total = Decimal("0.000")
    for item in items:
        product = products_by_id[item.catalog_item_id]
        unit_price = product.price_amount
        subtotal = unit_price * item.qty
        items_jsonb.append(
            {
                "catalog_item_id": str(item.catalog_item_id),
                "name": product.name,
                "qty": item.qty,
                "unit_price": str(unit_price),
                "currency": order_currency,
                "subtotal": str(subtotal),
            }
        )
        total += subtotal

    # Storefront: atomic raw-SQL decrement (original behaviour, unchanged)
    if source != "pos":
        for item in items:
            product = products_by_id[item.catalog_item_id]
            if not product.track_inventory:
                continue
            result_stock = await db.execute(
                text(
                    "UPDATE products "
                    "SET stock_qty = stock_qty - :qty "
                    "WHERE tenant_id = :tenant_id "
                    "  AND id = :product_id "
                    "  AND track_inventory = true "
                    "  AND stock_qty >= :qty"
                ),
                {
                    "qty": item.qty,
                    "tenant_id": str(tenant_id),
                    "product_id": str(item.catalog_item_id),
                },
            )
            if result_stock.rowcount == 0:
                raise HTTPException(
                    status_code=409,
                    detail=f"Insufficient stock for product '{product.name}'",
                )

    order_number = await get_next_order_number(db, str(tenant_id))

    order = Order(
        tenant_id=tenant_id,
        order_number=order_number,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        items=items_jsonb,
        total_amount=total,
        currency=order_currency,
        payment_notes=payment_notes,
        notes=notes,
        status=status,
        source=source,
        visit_id=visit_id,
    )
    db.add(order)
    await db.flush()

    # POS: auditable decrement via record_stock_movement (order.id now available)
    if source == "pos":
        for item in items:
            product = products_by_id[item.catalog_item_id]
            if not product.track_inventory:
                continue
            await record_stock_movement(
                db,
                tenant_id=tenant_id,
                product_id=item.catalog_item_id,
                delta_qty=-item.qty,
                reason="pos_sale",
                order_id=order.id,
                actor_user_id=actor_user_id,
                prevent_negative_stock=True,
                insufficient_stock_detail=(f"Insufficient stock for product '{product.name}'"),
            )

    return order
