"""Public read-only storefront endpoints (anonymous, tenant-scoped by slug).

Flow: slug -> lookup tenant -> SET LOCAL app.current_tenant -> query via RLS.
All in the same DB session. No tenant_id exposed in responses.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_with_slug
from app.models.category import Category
from app.models.media_asset import MediaAsset
from app.models.product import Product
from app.models.storefront_config import StorefrontConfig
from app.models.tenant import Tenant
from app.models.visit import Visit
from app.schemas.category import CategoryResponse
from app.schemas.common import PaginatedResponse
from app.schemas.product import PublicProductResponse
from app.schemas.public_storefront_config import PublicStorefrontConfigResponse
from app.schemas.visit import VisitCreateRequest, VisitCreateResponse
from app.services.ip_hash import hash_ip
from app.services.storage import presign_get

router = APIRouter()

DEFAULT_PAGE_SIZE = 20


def _public_product(
    product: Product,
    tenant: Tenant,
    image_url: str | None = None,
) -> PublicProductResponse:
    """Build public product response with effective_currency fallback."""
    return PublicProductResponse(
        id=product.id,
        category_id=product.category_id,
        name=product.name,
        description=product.description,
        price_amount=product.price_amount,
        effective_currency=product.currency or tenant.default_currency,
        sort_order=product.sort_order,
        metadata=product.metadata_,
        image_url=image_url,
    )


def _encode_cursor(sort_order: int, item_id: uuid.UUID) -> str:
    return f"{sort_order}:{item_id}"


def _decode_cursor(cursor: str) -> tuple[int, uuid.UUID]:
    try:
        sort_str, id_str = cursor.split(":", 1)
        return int(sort_str), uuid.UUID(id_str)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


@router.get("/{slug}/categories", response_model=PaginatedResponse[CategoryResponse])
async def list_public_categories(
    slug: str,
    cursor: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    db_tenant: tuple[AsyncSession, Tenant] = Depends(get_db_with_slug),
) -> PaginatedResponse[CategoryResponse]:
    db, _tenant = db_tenant

    stmt = (
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.sort_order, Category.id)
    )

    if cursor is not None:
        cursor_sort, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(
            tuple_(Category.sort_order, Category.id) > tuple_(cursor_sort, cursor_id)
        )

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]

    return PaginatedResponse(
        items=[CategoryResponse.model_validate(c) for c in items],
        next_cursor=(
            _encode_cursor(items[-1].sort_order, items[-1].id) if has_more and items else None
        ),
        has_more=has_more,
    )


@router.get("/{slug}/products", response_model=PaginatedResponse[PublicProductResponse])
async def list_public_products(
    slug: str,
    category_id: uuid.UUID | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    db_tenant: tuple[AsyncSession, Tenant] = Depends(get_db_with_slug),
) -> PaginatedResponse[PublicProductResponse]:
    db, tenant = db_tenant

    stmt = (
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sort_order, Product.id)
    )

    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if cursor is not None:
        cursor_sort, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(tuple_(Product.sort_order, Product.id) > tuple_(cursor_sort, cursor_id))

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]

    # Batch-query primary image for each product (avoids N+1 DB queries)
    image_urls: dict[uuid.UUID, str] = {}
    if items:
        product_ids = [p.id for p in items]
        media_stmt = (
            select(MediaAsset)
            .where(MediaAsset.product_id.in_(product_ids))
            .order_by(
                MediaAsset.sort_order,
                MediaAsset.created_at,
                MediaAsset.id,
            )
        )
        media_result = await db.execute(media_stmt)
        # Keep only the first media asset per product (deterministic primary)
        for asset in media_result.scalars().all():
            if asset.product_id not in image_urls:
                image_urls[asset.product_id] = presign_get(asset.s3_key)

    return PaginatedResponse(
        items=[_public_product(p, tenant, image_url=image_urls.get(p.id)) for p in items],
        next_cursor=(
            _encode_cursor(items[-1].sort_order, items[-1].id) if has_more and items else None
        ),
        has_more=has_more,
    )


@router.get("/{slug}/config", response_model=PublicStorefrontConfigResponse)
async def get_public_storefront_config(
    slug: str,
    db_tenant: tuple[AsyncSession, Tenant] = Depends(get_db_with_slug),
) -> PublicStorefrontConfigResponse:
    """Return public branding config for the storefront.

    No auth required. Returns defaults (all nulls) if tenant has no config.
    logo_url is a presigned S3 GET URL (15-min expiry) when logo_s3_key exists.
    custom_css is intentionally omitted to prevent arbitrary CSS injection.
    """
    db, tenant = db_tenant

    result = await db.execute(
        select(StorefrontConfig).where(StorefrontConfig.tenant_id == tenant.id)
    )
    config = result.scalar_one_or_none()

    if config is None:
        return PublicStorefrontConfigResponse()

    logo_url = presign_get(config.logo_s3_key) if config.logo_s3_key else None

    return PublicStorefrontConfigResponse(
        hero_text=config.hero_text,
        primary_color=config.primary_color,
        secondary_color=config.secondary_color,
        logo_url=logo_url,
    )


@router.post("/{slug}/visit", response_model=VisitCreateResponse, status_code=201)
async def capture_visit(
    slug: str,
    body: VisitCreateRequest,
    request: Request,
    db_tenant: tuple[AsyncSession, Tenant] = Depends(get_db_with_slug),
) -> VisitCreateResponse:
    """Record an anonymous storefront visit (UTM + session tracking).

    Client IP is salted-hashed (SHA-256) for privacy — no raw IP stored.
    Prefers X-Forwarded-For (first value) when behind a proxy, falls back
    to request.client.host.
    """
    db, tenant = db_tenant

    # Resolve client IP: prefer X-Forwarded-For first value, then direct
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        raw_ip = forwarded.split(",")[0].strip()
    elif request.client:
        raw_ip = request.client.host
    else:
        raw_ip = None

    visit = Visit(
        tenant_id=tenant.id,
        session_id=body.session_id,
        ip_hash=hash_ip(raw_ip),
        user_agent=request.headers.get("user-agent"),
        utm_source=body.utm_source,
        utm_medium=body.utm_medium,
        utm_campaign=body.utm_campaign,
        utm_content=body.utm_content,
        utm_term=body.utm_term,
    )
    db.add(visit)
    await db.flush()

    return VisitCreateResponse(visit_id=visit.id)
