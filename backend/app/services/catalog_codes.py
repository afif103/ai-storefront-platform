"""Shared catalog code uniqueness checks across products and variants.

A SKU or barcode must be unique within the combined product + product_variant
namespace for a tenant, so POS scan/search stays unambiguous. DB partial unique
indexes enforce uniqueness within each table; this helper adds the cross-table
guard at the application layer. It is not fully race-proof across tables and
intentionally does not introduce a shared registry table.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_variant import ProductVariant


async def _assert_code_unused(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    column: str,
    value: str,
    exclude_product_id: uuid.UUID | None,
    exclude_variant_id: uuid.UUID | None,
    label: str,
) -> None:
    product_stmt = select(Product.id).where(
        Product.tenant_id == tenant_id, getattr(Product, column) == value
    )
    if exclude_product_id is not None:
        product_stmt = product_stmt.where(Product.id != exclude_product_id)
    if (await db.execute(product_stmt.limit(1))).first() is not None:
        raise HTTPException(status_code=409, detail=f"{label} already in use")

    variant_stmt = select(ProductVariant.id).where(
        ProductVariant.tenant_id == tenant_id, getattr(ProductVariant, column) == value
    )
    if exclude_variant_id is not None:
        variant_stmt = variant_stmt.where(ProductVariant.id != exclude_variant_id)
    if (await db.execute(variant_stmt.limit(1))).first() is not None:
        raise HTTPException(status_code=409, detail=f"{label} already in use")


async def assert_catalog_code_available(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    sku: str | None,
    barcode: str | None,
    exclude_product_id: uuid.UUID | None = None,
    exclude_variant_id: uuid.UUID | None = None,
) -> None:
    """Raise HTTP 409 if sku or barcode is already used by a product or variant.

    Checks both the products and product_variants tables within the tenant,
    excluding the row being created or updated. RLS also scopes queries to the
    tenant; the explicit tenant_id filter is defense-in-depth.
    """
    if sku is not None:
        await _assert_code_unused(
            db, tenant_id, "sku", sku, exclude_product_id, exclude_variant_id, "SKU"
        )
    if barcode is not None:
        await _assert_code_unused(
            db, tenant_id, "barcode", barcode, exclude_product_id, exclude_variant_id, "Barcode"
        )
