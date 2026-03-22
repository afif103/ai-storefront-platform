"""Authenticated CRUD endpoints for products."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete as sa_delete
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_with_tenant, require_role
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.common import BulkDeleteRequest, BulkDeleteResponse, PaginatedResponse
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    RestockRequest,
    StockMovementResponse,
)
from app.services.inventory import record_stock_movement

router = APIRouter()

DEFAULT_PAGE_SIZE = 20


async def _get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    """Fetch tenant row; raise 500 if missing (should never happen)."""
    tenant = await db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=500, detail="Tenant not found")
    return tenant


def _product_response(product: Product, tenant: Tenant) -> ProductResponse:
    """Build ProductResponse with effective_currency fallback."""
    is_low_stock = (
        product.track_inventory
        and product.low_stock_threshold is not None
        and product.low_stock_threshold > 0
        and product.stock_qty is not None
        and 0 < product.stock_qty <= product.low_stock_threshold
    )
    return ProductResponse(
        id=product.id,
        category_id=product.category_id,
        name=product.name,
        description=product.description,
        name_ar=product.name_ar,
        description_ar=product.description_ar,
        price_amount=product.price_amount,
        currency=product.currency,
        effective_currency=product.currency or tenant.default_currency,
        is_active=product.is_active,
        sort_order=product.sort_order,
        metadata=product.metadata_,
        track_inventory=product.track_inventory,
        stock_qty=product.stock_qty,
        low_stock_threshold=product.low_stock_threshold,
        is_low_stock=is_low_stock,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def _encode_cursor(product: Product) -> str:
    return f"{product.created_at.isoformat()}|{product.id}"


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        dt_str, id_str = cursor.split("|", 1)
        return datetime.fromisoformat(dt_str), uuid.UUID(id_str)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


@router.get("", response_model=PaginatedResponse[ProductResponse])
async def list_products(
    category_id: uuid.UUID | None = Query(None),
    is_active: bool | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> PaginatedResponse[ProductResponse]:
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    tenant = await _get_tenant(db, tenant_id)

    stmt = select(Product).order_by(Product.created_at.desc(), Product.id.desc())

    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if is_active is not None:
        stmt = stmt.where(Product.is_active == is_active)
    if cursor is not None:
        cursor_dt, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(tuple_(Product.created_at, Product.id) < tuple_(cursor_dt, cursor_id))

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]

    return PaginatedResponse(
        items=[_product_response(p, tenant) for p in items],
        next_cursor=_encode_cursor(items[-1]) if has_more and items else None,
        has_more=has_more,
    )


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    body: ProductCreate,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> ProductResponse:
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    tenant = await _get_tenant(db, tenant_id)

    product = Product(
        tenant_id=tenant_id,
        category_id=body.category_id,
        name=body.name,
        description=body.description,
        name_ar=body.name_ar,
        description_ar=body.description_ar,
        price_amount=body.price_amount,
        currency=body.currency,
        is_active=body.is_active,
        sort_order=body.sort_order,
        metadata_=body.metadata,
        track_inventory=body.track_inventory,
        stock_qty=body.stock_qty,
        low_stock_threshold=body.low_stock_threshold,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return _product_response(product, tenant)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> ProductResponse:
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    tenant = await _get_tenant(db, tenant_id)

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return _product_response(product, tenant)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> ProductResponse:
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    tenant = await _get_tenant(db, tenant_id)

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        attr = "metadata_" if field == "metadata" else field
        setattr(product, attr, value)

    await db.flush()
    await db.refresh(product)
    return _product_response(product, tenant)


@router.post("/{product_id}/restock", response_model=ProductResponse)
async def restock_product(
    product_id: uuid.UUID,
    body: RestockRequest,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> ProductResponse:
    """Add stock to a tracked-inventory product via audited movement."""
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    tenant = await _get_tenant(db, tenant_id)

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.track_inventory:
        raise HTTPException(
            status_code=422,
            detail="Cannot restock a product that does not track inventory",
        )

    await record_stock_movement(
        db,
        tenant_id=tenant_id,
        product_id=product.id,
        delta_qty=body.qty,
        reason="manual_restock",
        note=body.note,
        actor_user_id=user.id,
    )
    await db.refresh(product)
    return _product_response(product, tenant)


@router.get(
    "/{product_id}/stock-movements",
    response_model=PaginatedResponse[StockMovementResponse],
)
async def list_stock_movements(
    product_id: uuid.UUID,
    cursor: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> PaginatedResponse[StockMovementResponse]:
    """List stock movements for a product, newest first."""
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    # Verify product exists
    prod_result = await db.execute(select(Product).where(Product.id == product_id))
    if prod_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Product not found")

    stmt = (
        select(StockMovement)
        .where(StockMovement.product_id == product_id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
    )

    if cursor is not None:
        cursor_dt, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(
            tuple_(StockMovement.created_at, StockMovement.id) < tuple_(cursor_dt, cursor_id)
        )

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]

    def _movement_cursor(m: StockMovement) -> str:
        return f"{m.created_at.isoformat()}|{m.id}"

    return PaginatedResponse(
        items=[StockMovementResponse.model_validate(m) for m in items],
        next_cursor=_movement_cursor(items[-1]) if has_more and items else None,
        has_more=has_more,
    )


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_products(
    body: BulkDeleteRequest,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> BulkDeleteResponse:
    """Delete multiple products in a single transaction. RLS scopes to tenant."""
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    result = await db.execute(
        sa_delete(Product).where(Product.id.in_(body.ids)).returning(Product.id)
    )
    deleted_ids = result.fetchall()
    await db.flush()
    return BulkDeleteResponse(deleted=len(deleted_ids))


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> None:
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    await db.delete(product)
    await db.flush()
