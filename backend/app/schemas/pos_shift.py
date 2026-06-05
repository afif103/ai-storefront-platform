"""POS shift request/response schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PosShiftOpenRequest(BaseModel):
    starting_cash: Decimal = Field(..., ge=0, decimal_places=3)


class PosShiftCloseRequest(BaseModel):
    counted_cash: Decimal = Field(..., ge=0, decimal_places=3)
    notes: str | None = Field(None, max_length=2000)


class PosShiftResponse(BaseModel):
    id: uuid.UUID
    status: str
    starting_cash: Decimal
    cash_sales: Decimal
    expected_cash: Decimal
    counted_cash: Decimal | None = None
    variance: Decimal | None = None
    opened_at: datetime
    opened_by: uuid.UUID | None = None
    closed_at: datetime | None = None
    closed_by: uuid.UUID | None = None
    notes: str | None = None


class PosCurrentShiftResponse(BaseModel):
    shift: PosShiftResponse | None = None
