"""Pledge request/response schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PledgeCreateRequest(BaseModel):
    pledgor_name: str = Field(..., min_length=1, max_length=255)
    pledgor_phone: str | None = Field(None, max_length=50)
    pledgor_email: str | None = Field(None, max_length=255)
    amount: Decimal = Field(..., gt=0, decimal_places=3)
    currency: str = Field("KWD", min_length=3, max_length=3)
    target_date: date
    product_id: uuid.UUID | None = None
    payment_notes: str | None = Field(None, max_length=2000)
    notes: str | None = Field(None, max_length=2000)
    visit_id: uuid.UUID | None = None


class PledgeListItem(BaseModel):
    id: uuid.UUID
    pledge_number: str
    pledgor_name: str
    pledgor_phone: str | None
    amount: Decimal
    currency: str
    target_date: date
    status: str
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class PledgeCreateResponse(BaseModel):
    id: uuid.UUID
    pledge_number: str
    amount: Decimal
    currency: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
