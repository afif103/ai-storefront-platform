"""Pydantic schemas for analytics ingest + dashboard summary."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
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


# ---------------------------------------------------------------------------
# Sales reporting (authenticated endpoint) — M13.1 unified online + POS sales
# ---------------------------------------------------------------------------


class ChannelSales(BaseModel):
    source: str
    order_count: int
    gross_sales: Decimal


class PaymentMethodSales(BaseModel):
    payment_method: str | None
    order_count: int
    gross_sales: Decimal


class SalesSummaryResponse(BaseModel):
    currency: str
    total_sales: Decimal
    total_orders: int
    average_order_value: Decimal
    storefront_sales: Decimal
    storefront_orders: int
    pos_sales: Decimal
    pos_orders: int
    cancelled_orders: int
    cancelled_amount: Decimal
    by_channel: list[ChannelSales]
    by_payment_method: list[PaymentMethodSales]


# ---------------------------------------------------------------------------
# Revenue analytics (authenticated endpoint) — M13.2 channel/product/time
# ---------------------------------------------------------------------------


class DailyRevenuePoint(BaseModel):
    date: str
    order_count: int
    gross_sales: Decimal  # SUM(order.total_amount) — includes shipping
    storefront_sales: Decimal
    pos_sales: Decimal


class ProductRevenue(BaseModel):
    product_id: str
    name: str
    qty_sold: int
    gross_sales: Decimal  # SUM(line-item subtotal) — excludes shipping


class RevenueAnalyticsResponse(BaseModel):
    currency: str
    by_day: list[DailyRevenuePoint]
    top_products: list[ProductRevenue]


# ---------------------------------------------------------------------------
# POS today snapshot (authenticated endpoint) — M13.3 POS dashboard widgets
# ---------------------------------------------------------------------------


class PosTodayResponse(BaseModel):
    currency: str
    date: str  # echo of the requested local date
    pos_sales: Decimal  # SUM(total_amount) — POS, non-cancelled, this day
    pos_order_count: int
    by_payment_method: list[PaymentMethodSales]
    top_products: list[ProductRevenue]
