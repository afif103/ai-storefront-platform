"""Dashboard analytics summary endpoint (authenticated, tenant-scoped)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_with_tenant, require_role
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    ChannelSales,
    DailyPoint,
    DailyRevenuePoint,
    FunnelStep,
    PaymentMethodSales,
    ProductRevenue,
    RevenueAnalyticsResponse,
    SalesSummaryResponse,
)

router = APIRouter()

_MAX_RANGE_DAYS = 180

# Funnel steps in order — rates computed relative to the first step
_FUNNEL_STEPS = (
    "storefront_view",
    "product_view",
    "add_to_cart",
    "begin_checkout",
    "submit_order",
    "submit_donation",
    "submit_pledge",
)

_MONEY_QUANT = Decimal("0.001")


def _money(value: Decimal | None) -> Decimal:
    """Coerce a SQL aggregate result (Decimal | None) to a 3-decimal Decimal."""
    if value is None:
        return Decimal("0.000")
    return Decimal(value).quantize(_MONEY_QUANT)


@router.get("/analytics/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> AnalyticsSummaryResponse:
    """Return analytics summary for the current tenant within a date range."""
    db, tenant_id = db_tenant
    tid = str(tenant_id)

    # Validate range
    if to_date <= from_date:
        raise HTTPException(status_code=422, detail="'to' must be after 'from'")
    if (to_date - from_date).days > _MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"Date range must not exceed {_MAX_RANGE_DAYS} days",
        )

    # to_date is exclusive upper bound (full day inclusion)
    to_exclusive = to_date + timedelta(days=1)
    params = {"tenant_id": tid, "from_dt": from_date, "to_dt": to_exclusive}

    # --- Visitors & sessions from attribution_sessions ---
    counts_result = await db.execute(
        text(
            """
            SELECT
                COUNT(DISTINCT visitor_id) AS visitors,
                COUNT(*) AS sessions
            FROM attribution_sessions
            WHERE tenant_id = :tenant_id
              AND last_seen_at >= :from_dt
              AND last_seen_at < :to_dt
            """
        ),
        params,
    )
    row = counts_result.one()
    visitors = row.visitors
    sessions = row.sessions

    # --- Event counts ---
    event_counts_result = await db.execute(
        text(
            """
            SELECT event_name, COUNT(*) AS cnt
            FROM attribution_events
            WHERE tenant_id = :tenant_id
              AND occurred_at >= :from_dt
              AND occurred_at < :to_dt
            GROUP BY event_name
            """
        ),
        params,
    )
    event_counts: dict[str, int] = {r.event_name: r.cnt for r in event_counts_result.all()}

    # --- Funnel ---
    top_count = event_counts.get(_FUNNEL_STEPS[0], 0)
    funnel: list[FunnelStep] = []
    for step in _FUNNEL_STEPS:
        count = event_counts.get(step, 0)
        rate = (count / top_count) if top_count > 0 else 0.0
        funnel.append(FunnelStep(event_name=step, count=count, rate=round(rate, 4)))

    # --- Daily series ---
    daily_result = await db.execute(
        text(
            """
            SELECT
                date_trunc('day', occurred_at)::date AS day,
                COUNT(*) FILTER (WHERE event_name = 'storefront_view') AS storefront_views,
                COUNT(*) FILTER (
                    WHERE event_name IN ('submit_order', 'submit_donation', 'submit_pledge')
                ) AS submissions
            FROM attribution_events
            WHERE tenant_id = :tenant_id
              AND occurred_at >= :from_dt
              AND occurred_at < :to_dt
            GROUP BY day
            ORDER BY day
            """
        ),
        params,
    )
    daily_series = [
        DailyPoint(
            date=str(r.day),
            storefront_views=r.storefront_views,
            submissions=r.submissions,
        )
        for r in daily_result.all()
    ]

    return AnalyticsSummaryResponse(
        visitors=visitors,
        sessions=sessions,
        event_counts=event_counts,
        funnel=funnel,
        daily_series=daily_series if daily_series else None,
    )


@router.get("/analytics/sales", response_model=SalesSummaryResponse)
async def get_sales_summary(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> SalesSummaryResponse:
    """Unified online + POS sales summary for the current tenant (read-only).

    Revenue, AOV, channel, and payment-method figures cover non-cancelled orders
    only; cancelled orders are reported separately. Member role or higher.
    """
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    # Validate range (same rules as /analytics/summary)
    if to_date <= from_date:
        raise HTTPException(status_code=422, detail="'to' must be after 'from'")
    if (to_date - from_date).days > _MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"Date range must not exceed {_MAX_RANGE_DAYS} days",
        )

    # to_date is exclusive upper bound (full day inclusion)
    to_exclusive = to_date + timedelta(days=1)
    params = {"tenant_id": str(tenant_id), "from_dt": from_date, "to_dt": to_exclusive}

    # --- Channel breakdown + totals (non-cancelled orders only) ---
    channel_result = await db.execute(
        text(
            """
            SELECT source,
                   COUNT(*) AS order_count,
                   COALESCE(SUM(total_amount), 0) AS gross_sales
            FROM orders
            WHERE tenant_id = :tenant_id
              AND status <> 'cancelled'
              AND created_at >= :from_dt
              AND created_at < :to_dt
            GROUP BY source
            ORDER BY source
            """
        ),
        params,
    )
    by_channel: list[ChannelSales] = []
    storefront_sales = Decimal("0.000")
    storefront_orders = 0
    pos_sales = Decimal("0.000")
    pos_orders = 0
    total_sales = Decimal("0.000")
    total_orders = 0
    for r in channel_result.all():
        gross = _money(r.gross_sales)
        by_channel.append(
            ChannelSales(source=r.source, order_count=r.order_count, gross_sales=gross)
        )
        total_sales += gross
        total_orders += r.order_count
        if r.source == "storefront":
            storefront_sales = gross
            storefront_orders = r.order_count
        elif r.source == "pos":
            pos_sales = gross
            pos_orders = r.order_count
    total_sales = total_sales.quantize(_MONEY_QUANT)

    # Average order value: 3dp, 0.000 when there are no non-cancelled orders
    if total_orders > 0:
        average_order_value = _money(total_sales / Decimal(total_orders))
    else:
        average_order_value = Decimal("0.000")

    # --- Cancelled orders (reported separately, excluded from revenue) ---
    cancelled_result = await db.execute(
        text(
            """
            SELECT COUNT(*) AS cancelled_orders,
                   COALESCE(SUM(total_amount), 0) AS cancelled_amount
            FROM orders
            WHERE tenant_id = :tenant_id
              AND status = 'cancelled'
              AND created_at >= :from_dt
              AND created_at < :to_dt
            """
        ),
        params,
    )
    crow = cancelled_result.one()
    cancelled_orders = crow.cancelled_orders
    cancelled_amount = _money(crow.cancelled_amount)

    # --- Payment-method breakdown (non-cancelled; NULL bucket preserved) ---
    payment_result = await db.execute(
        text(
            """
            SELECT payment_method,
                   COUNT(*) AS order_count,
                   COALESCE(SUM(total_amount), 0) AS gross_sales
            FROM orders
            WHERE tenant_id = :tenant_id
              AND status <> 'cancelled'
              AND created_at >= :from_dt
              AND created_at < :to_dt
            GROUP BY payment_method
            ORDER BY payment_method NULLS LAST
            """
        ),
        params,
    )
    by_payment_method = [
        PaymentMethodSales(
            payment_method=r.payment_method,
            order_count=r.order_count,
            gross_sales=_money(r.gross_sales),
        )
        for r in payment_result.all()
    ]

    # --- Currency (single-currency-per-tenant; default KWD when no rows) ---
    currency_result = await db.execute(
        text(
            """
            SELECT currency
            FROM orders
            WHERE tenant_id = :tenant_id
              AND created_at >= :from_dt
              AND created_at < :to_dt
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        params,
    )
    currency = currency_result.scalar_one_or_none() or "KWD"

    return SalesSummaryResponse(
        currency=currency,
        total_sales=total_sales,
        total_orders=total_orders,
        average_order_value=average_order_value,
        storefront_sales=storefront_sales,
        storefront_orders=storefront_orders,
        pos_sales=pos_sales,
        pos_orders=pos_orders,
        cancelled_orders=cancelled_orders,
        cancelled_amount=cancelled_amount,
        by_channel=by_channel,
        by_payment_method=by_payment_method,
    )


@router.get("/analytics/revenue", response_model=RevenueAnalyticsResponse)
async def get_revenue_analytics(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> RevenueAnalyticsResponse:
    """Revenue analytics by day (channel-split) and top products (read-only).

    Daily figures use order.total_amount (includes shipping); top-product figures
    use line-item subtotals from the orders.items JSONB (exclude shipping). Both
    cover non-cancelled orders only. Member role or higher.
    """
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    # Validate range (same rules as /analytics/summary and /analytics/sales)
    if to_date <= from_date:
        raise HTTPException(status_code=422, detail="'to' must be after 'from'")
    if (to_date - from_date).days > _MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"Date range must not exceed {_MAX_RANGE_DAYS} days",
        )

    # to_date is exclusive upper bound (full day inclusion)
    to_exclusive = to_date + timedelta(days=1)
    params = {"tenant_id": str(tenant_id), "from_dt": from_date, "to_dt": to_exclusive}

    # --- Daily revenue (non-cancelled), with per-channel split ---
    daily_result = await db.execute(
        text(
            """
            SELECT
                date_trunc('day', created_at)::date AS day,
                COUNT(*) AS order_count,
                COALESCE(SUM(total_amount), 0) AS gross_sales,
                COALESCE(
                    SUM(total_amount) FILTER (WHERE source = 'storefront'), 0
                ) AS storefront_sales,
                COALESCE(
                    SUM(total_amount) FILTER (WHERE source = 'pos'), 0
                ) AS pos_sales
            FROM orders
            WHERE tenant_id = :tenant_id
              AND status <> 'cancelled'
              AND created_at >= :from_dt
              AND created_at < :to_dt
            GROUP BY day
            ORDER BY day
            """
        ),
        params,
    )
    by_day = [
        DailyRevenuePoint(
            date=str(r.day),
            order_count=r.order_count,
            gross_sales=_money(r.gross_sales),
            storefront_sales=_money(r.storefront_sales),
            pos_sales=_money(r.pos_sales),
        )
        for r in daily_result.all()
    ]

    # --- Top products (non-cancelled), aggregated over the items JSONB ---
    # Variants roll up to their parent product via catalog_item_id. Grouping on
    # the stable id (not the snapshot name) is robust to mid-window renames;
    # MAX(name) supplies a representative display label. Subtotals exclude
    # shipping by construction (shipping is not part of any line item).
    top_result = await db.execute(
        text(
            """
            SELECT
                elem->>'catalog_item_id' AS product_id,
                MAX(elem->>'name') AS name,
                SUM((elem->>'qty')::int) AS qty_sold,
                SUM((elem->>'subtotal')::numeric) AS gross_sales
            FROM orders,
                 LATERAL jsonb_array_elements(items) AS elem
            WHERE tenant_id = :tenant_id
              AND status <> 'cancelled'
              AND created_at >= :from_dt
              AND created_at < :to_dt
            GROUP BY elem->>'catalog_item_id'
            ORDER BY gross_sales DESC
            LIMIT 10
            """
        ),
        params,
    )
    top_products = [
        ProductRevenue(
            product_id=r.product_id,
            name=r.name,
            qty_sold=r.qty_sold,
            gross_sales=_money(r.gross_sales),
        )
        for r in top_result.all()
    ]

    # --- Currency (single-currency-per-tenant; default KWD when no rows) ---
    currency_result = await db.execute(
        text(
            """
            SELECT currency
            FROM orders
            WHERE tenant_id = :tenant_id
              AND created_at >= :from_dt
              AND created_at < :to_dt
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        params,
    )
    currency = currency_result.scalar_one_or_none() or "KWD"

    return RevenueAnalyticsResponse(
        currency=currency,
        by_day=by_day,
        top_products=top_products,
    )
