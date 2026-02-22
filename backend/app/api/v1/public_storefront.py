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
from app.models.product import Product
from app.models.tenant import Tenant
from app.models.visit import Visit
from app.schemas.category import CategoryResponse
from app.schemas.common import PaginatedResponse
from app.schemas.product import PublicProductResponse
from app.schemas.visit import VisitCreateRequest, VisitCreateResponse
from app.services.ip_hash import hash_ip

router = APIRouter()

DEFAULT_PAGE_SIZE = 20


def _public_product(product: Product, tenant: Tenant) -> PublicProductResponse:
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

    return PaginatedResponse(
        items=[_public_product(p, tenant) for p in items],
        next_cursor=(
            _encode_cursor(items[-1].sort_order, items[-1].id) if has_more and items else None
        ),
        has_more=has_more,
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
