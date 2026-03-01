"""Status transition request/response schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


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
