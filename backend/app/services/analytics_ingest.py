"""Analytics event ingest: upsert visitor/session, dedupe, bulk insert events."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.schemas.analytics import AnalyticsIngestRequest, AnalyticsIngestResponse
from app.services.ai_quota import check_analytics_rate_limit
from app.services.ip_hash import hash_ip


def _resolve_ip(request: Request) -> str:
    """Extract and hash client IP from request."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        raw_ip = forwarded.split(",")[0].strip()
    elif request.client:
        raw_ip = request.client.host
    else:
        raw_ip = "unknown"
    return hash_ip(raw_ip) or "unknown"


async def handle_analytics_ingest(
    db: AsyncSession,
    tenant: Tenant,
    body: AnalyticsIngestRequest,
    request: Request,
) -> AnalyticsIngestResponse:
    """Process a batch of analytics events.

    1. Rate limit (per session + IP)
    2. Upsert visitor (first attribution sticks)
    3. Upsert session (first attribution sticks via COALESCE)
    4. Dedupe storefront_view (skip if same session within 10 min)
    5. Bulk insert events
    """
    tenant_id = str(tenant.id)
    ip_hash = _resolve_ip(request)

    # 1. Rate limit
    within_limit = await check_analytics_rate_limit(tenant_id, str(body.session_id), ip_hash)
    if not within_limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # 2. Upsert visitor — ON CONFLICT matches UNIQUE (tenant_id, visitor_id)
    await db.execute(
        text(
            """
            INSERT INTO attribution_visitors (visitor_id, tenant_id, first_seen_at, last_seen_at)
            VALUES (:visitor_id, :tenant_id, now(), now())
            ON CONFLICT (tenant_id, visitor_id)
            DO UPDATE SET last_seen_at = now()
            """
        ),
        {"visitor_id": str(body.visitor_id), "tenant_id": tenant_id},
    )

    # 3. Upsert session — ON CONFLICT matches UNIQUE (tenant_id, session_id)
    #    COALESCE keeps first non-null attribution; NULLIF treats '' as NULL
    await db.execute(
        text(
            """
            INSERT INTO attribution_sessions
                (session_id, tenant_id, visitor_id, first_seen_at, last_seen_at,
                 utm_source, utm_medium, utm_campaign, utm_content, utm_term, referrer)
            VALUES
                (:session_id, :tenant_id, :visitor_id, now(), now(),
                 :utm_source, :utm_medium, :utm_campaign, :utm_content, :utm_term, :referrer)
            ON CONFLICT (tenant_id, session_id)
            DO UPDATE SET
                last_seen_at = now(),
                utm_source   = COALESCE(attribution_sessions.utm_source,
                                        NULLIF(EXCLUDED.utm_source, '')),
                utm_medium   = COALESCE(attribution_sessions.utm_medium,
                                        NULLIF(EXCLUDED.utm_medium, '')),
                utm_campaign = COALESCE(attribution_sessions.utm_campaign,
                                        NULLIF(EXCLUDED.utm_campaign, '')),
                utm_content  = COALESCE(attribution_sessions.utm_content,
                                        NULLIF(EXCLUDED.utm_content, '')),
                utm_term     = COALESCE(attribution_sessions.utm_term,
                                        NULLIF(EXCLUDED.utm_term, '')),
                referrer     = COALESCE(attribution_sessions.referrer,
                                        NULLIF(EXCLUDED.referrer, ''))
            """
        ),
        {
            "session_id": str(body.session_id),
            "tenant_id": tenant_id,
            "visitor_id": str(body.visitor_id),
            "utm_source": body.utm_source,
            "utm_medium": body.utm_medium,
            "utm_campaign": body.utm_campaign,
            "utm_content": body.utm_content,
            "utm_term": body.utm_term,
            "referrer": body.referrer,
        },
    )

    # 4. Dedupe storefront_view — tenant-scoped, uses ix_attr_events_dedupe index
    cutoff = datetime.now(UTC) - timedelta(minutes=10)
    dedupe_result = await db.execute(
        text(
            """
            SELECT 1 FROM attribution_events
            WHERE tenant_id = :tenant_id
              AND session_id = :session_id
              AND event_name = 'storefront_view'
              AND occurred_at > :cutoff
            LIMIT 1
            """
        ),
        {
            "tenant_id": tenant_id,
            "session_id": str(body.session_id),
            "cutoff": cutoff,
        },
    )
    has_recent_view = dedupe_result.scalar_one_or_none() is not None

    # 5. Insert events
    accepted = 0
    skipped = 0
    for event in body.events:
        if event.name == "storefront_view" and has_recent_view:
            skipped += 1
            continue

        occurred_at = event.ts if event.ts is not None else datetime.now(UTC)
        await db.execute(
            text(
                """
                INSERT INTO attribution_events
                    (tenant_id, session_id, occurred_at, event_name, props)
                VALUES
                    (:tenant_id, :session_id, :occurred_at, :event_name, :props::jsonb)
                """
            ),
            {
                "tenant_id": tenant_id,
                "session_id": str(body.session_id),
                "occurred_at": occurred_at,
                "event_name": event.name,
                "props": None if event.props is None else json.dumps(event.props),
            },
        )
        accepted += 1

        # After first storefront_view insert, block further dupes in this batch
        if event.name == "storefront_view":
            has_recent_view = True

    await db.flush()

    return AnalyticsIngestResponse(accepted=accepted, skipped=skipped)
