"""Order request/response schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.payment import normalize_optional_payment_method


class OrderItemRequest(BaseModel):
    catalog_item_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    qty: int = Field(..., ge=1)


class OrderCreateRequest(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_phone: str | None = Field(None, max_length=50)
    customer_email: str | None = Field(None, max_length=255)
    items: list[OrderItemRequest] = Field(..., min_length=1)
    payment_notes: str | None = Field(None, max_length=2000)
    notes: str | None = Field(None, max_length=2000)
    visit_id: uuid.UUID | None = None
    payment_method: str | None = None

    @field_validator("payment_method")
    @classmethod
    def _normalize_payment_method(cls, v: str | None) -> str | None:
        return normalize_optional_payment_method(v)


class OrderListItem(BaseModel):
    id: uuid.UUID
    order_number: str
    customer_name: str
    customer_phone: str | None
    total_amount: Decimal
    currency: str
    status: str
    source: str
    created_at: datetime
    updated_at: datetime | None
    cancel_reason: str | None = None

    model_config = {"from_attributes": True}


class OrderDetailResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    customer_name: str
    customer_phone: str | None
    customer_email: str | None
    customer_id: uuid.UUID | None
    items: list[Any]
    total_amount: Decimal
    currency: str
    status: str
    source: str
    payment_method: str | None
    payment_notes: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class OrderCreateResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    customer_name: str
    customer_id: uuid.UUID | None = None
    items: list[Any]
    total_amount: Decimal
    currency: str
    status: str
    source: str
    payment_method: str | None = None
    cancel_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
