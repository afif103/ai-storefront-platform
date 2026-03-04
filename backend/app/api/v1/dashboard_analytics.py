"""Dashboard analytics summary endpoint (authenticated, tenant-scoped)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_with_tenant
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    DailyPoint,
    FunnelStep,
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
