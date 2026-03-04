"""Pydantic schemas for analytics ingest + dashboard summary."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.attribution_event import ALLOWED_EVENT_NAMES

# ---------------------------------------------------------------------------
# Ingest (public batch endpoint)
# ---------------------------------------------------------------------------


class AnalyticsEvent(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    ts: datetime | None = None
    props: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def name_must_be_allowed(cls, v: str) -> str:
        if v not in ALLOWED_EVENT_NAMES:
            msg = f"Invalid event name '{v}'. Allowed: {', '.join(ALLOWED_EVENT_NAMES)}"
            raise ValueError(msg)
        return v

    @field_validator("props")
    @classmethod
    def props_size_limit(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is not None and len(json.dumps(v, default=str)) > 4096:
            raise ValueError("props JSON must be <= 4096 bytes")
        return v


class AnalyticsIngestRequest(BaseModel):
    visitor_id: uuid.UUID
    session_id: uuid.UUID
    utm_source: str | None = Field(None, max_length=255)
    utm_medium: str | None = Field(None, max_length=255)
    utm_campaign: str | None = Field(None, max_length=255)
    utm_content: str | None = Field(None, max_length=255)
    utm_term: str | None = Field(None, max_length=255)
    referrer: str | None = Field(None, max_length=2000)
    events: list[AnalyticsEvent] = Field(..., min_length=1, max_length=20)


class AnalyticsIngestResponse(BaseModel):
    accepted: int
    skipped: int


# ---------------------------------------------------------------------------
# Dashboard summary (authenticated endpoint)
# ---------------------------------------------------------------------------


class FunnelStep(BaseModel):
    event_name: str
    count: int
    rate: float


class DailyPoint(BaseModel):
    date: str
    storefront_views: int
    submissions: int


class AnalyticsSummaryResponse(BaseModel):
    visitors: int
    sessions: int
    event_counts: dict[str, int]
    funnel: list[FunnelStep]
    daily_series: list[DailyPoint] | None = None
