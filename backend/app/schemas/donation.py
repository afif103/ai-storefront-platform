"""Donation request/response schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class DonationCreateRequest(BaseModel):
    donor_name: str = Field(..., min_length=1, max_length=255)
    donor_phone: str | None = Field(None, max_length=50)
    donor_email: str | None = Field(None, max_length=255)
    amount: Decimal = Field(..., gt=0, decimal_places=3)
    currency: str = Field("KWD", min_length=3, max_length=3)
    campaign: str | None = Field(None, max_length=255)
    receipt_requested: bool = False
    product_id: uuid.UUID | None = None
    payment_notes: str | None = Field(None, max_length=2000)
    notes: str | None = Field(None, max_length=2000)
    visit_id: uuid.UUID | None = None


class DonationListItem(BaseModel):
    id: uuid.UUID
    donation_number: str
    donor_name: str
    donor_phone: str | None
    amount: Decimal
    currency: str
    campaign: str | None
    status: str
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class DonationCreateResponse(BaseModel):
    id: uuid.UUID
    donation_number: str
    amount: Decimal
    currency: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
