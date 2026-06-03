"""Authenticated CRUD endpoints for product variants (nested under products)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_with_tenant, require_role
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.product_variant import (
    ProductVariantCreate,
    ProductVariantResponse,
    ProductVariantUpdate,
)
from app.services.catalog_codes import assert_catalog_code_available

router = APIRouter()

DEFAULT_PAGE_SIZE = 20


def _encode_cursor(variant: ProductVariant) -> str:
    return f"{variant.sort_order}:{variant.id}"


def _decode_cursor(cursor: str) -> tuple[int, uuid.UUID]:
    try:
        sort_str, id_str = cursor.split(":", 1)
        return int(sort_str), uuid.UUID(id_str)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


async def _get_product_or_404(
    db: AsyncSession, tenant_id: uuid.UUID, product_id: uuid.UUID
) -> Product:
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


async def _get_variant_or_404(
    db: AsyncSession, tenant_id: uuid.UUID, product_id: uuid.UUID, variant_id: uuid.UUID
) -> ProductVariant:
    result = await db.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
            ProductVariant.tenant_id == tenant_id,
        )
    )
    variant = result.scalar_one_or_none()
    if variant is None:
        raise HTTPException(status_code=404, detail="Variant not found")
    return variant


@router.get("/{product_id}/variants", response_model=PaginatedResponse[ProductVariantResponse])
async def list_variants(
    product_id: uuid.UUID,
    cursor: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> PaginatedResponse[ProductVariantResponse]:
    db, tenant_id = db_tenant
    await require_role("cashier", db, tenant_id, user)

    await _get_product_or_404(db, tenant_id, product_id)

    stmt = (
        select(ProductVariant)
        .where(ProductVariant.product_id == product_id, ProductVariant.tenant_id == tenant_id)
        .order_by(ProductVariant.sort_order, ProductVariant.id)
    )
    if cursor is not None:
        cursor_sort, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(
            tuple_(ProductVariant.sort_order, ProductVariant.id) > tuple_(cursor_sort, cursor_id)
        )
    stmt = stmt.limit(limit + 1)

    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    has_more = len(rows) > limit
    items = rows[:limit]

    return PaginatedResponse(
        items=[ProductVariantResponse.model_validate(v) for v in items],
        next_cursor=_encode_cursor(items[-1]) if has_more and items else None,
        has_more=has_more,
    )


@router.post("/{product_id}/variants", response_model=ProductVariantResponse, status_code=201)
async def create_variant(
    product_id: uuid.UUID,
    body: ProductVariantCreate,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> ProductVariantResponse:
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    await _get_product_or_404(db, tenant_id, product_id)
    await assert_catalog_code_available(db, tenant_id, sku=body.sku, barcode=body.barcode)

    variant = ProductVariant(
        tenant_id=tenant_id,
        product_id=product_id,
        name=body.name,
        size=body.size,
        color=body.color,
        sku=body.sku,
        barcode=body.barcode,
        price_amount=body.price_amount,
        stock_qty=body.stock_qty,
        is_active=body.is_active,
        sort_order=body.sort_order,
    )
    db.add(variant)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Variant SKU or barcode already exists"
        ) from None
    await db.refresh(variant)
    return ProductVariantResponse.model_validate(variant)


@router.get("/{product_id}/variants/{variant_id}", response_model=ProductVariantResponse)
async def get_variant(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> ProductVariantResponse:
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    await _get_product_or_404(db, tenant_id, product_id)
    variant = await _get_variant_or_404(db, tenant_id, product_id, variant_id)
    return ProductVariantResponse.model_validate(variant)


@router.patch("/{product_id}/variants/{variant_id}", response_model=ProductVariantResponse)
async def update_variant(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    body: ProductVariantUpdate,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> ProductVariantResponse:
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    await _get_product_or_404(db, tenant_id, product_id)
    variant = await _get_variant_or_404(db, tenant_id, product_id, variant_id)

    update_data = body.model_dump(exclude_unset=True)
    sku_to_check = update_data.get("sku")
    barcode_to_check = update_data.get("barcode")
    await assert_catalog_code_available(
        db, tenant_id, sku=sku_to_check, barcode=barcode_to_check, exclude_variant_id=variant.id
    )

    for field, value in update_data.items():
        setattr(variant, field, value)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Variant SKU or barcode already exists"
        ) from None
    await db.refresh(variant)
    return ProductVariantResponse.model_validate(variant)


@router.delete("/{product_id}/variants/{variant_id}", status_code=204)
async def delete_variant(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> None:
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    await _get_product_or_404(db, tenant_id, product_id)
    variant = await _get_variant_or_404(db, tenant_id, product_id, variant_id)
    await db.delete(variant)
    await db.flush()
