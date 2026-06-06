"""Status transition request/response schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

FULFILLMENT_STATUSES = ("packed", "shipped", "delivered")


class StatusTransitionRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=50)


class OrderStatusResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    status: str
    total_amount: Decimal
    currency: str
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class DonationStatusResponse(BaseModel):
    id: uuid.UUID
    donation_number: str
    status: str
    amount: Decimal
    currency: str
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class PledgeStatusResponse(BaseModel):
    id: uuid.UUID
    pledge_number: str
    status: str
    amount: Decimal
    currency: str
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class OrderFulfillmentTransitionRequest(BaseModel):
    fulfillment_status: str = Field(..., min_length=1, max_length=20)

    @field_validator("fulfillment_status")
    @classmethod
    def _validate_fulfillment_status(cls, v: str) -> str:
        stripped = v.strip().lower()
        if stripped not in FULFILLMENT_STATUSES:
            raise ValueError(f"Invalid fulfillment_status: {v!r}")
        return stripped


class OrderFulfillmentResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    status: str
    fulfillment_status: str | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}
