"""Order request/response schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class OrderItemRequest(BaseModel):
    catalog_item_id: uuid.UUID
    qty: int = Field(..., ge=1)


class OrderCreateRequest(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_phone: str | None = Field(None, max_length=50)
    customer_email: str | None = Field(None, max_length=255)
    items: list[OrderItemRequest] = Field(..., min_length=1)
    payment_notes: str | None = Field(None, max_length=2000)
    notes: str | None = Field(None, max_length=2000)
    visit_id: uuid.UUID | None = None


class OrderListItem(BaseModel):
    id: uuid.UUID
    order_number: str
    customer_name: str
    customer_phone: str | None
    total_amount: Decimal
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class OrderCreateResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    total_amount: Decimal
    currency: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
