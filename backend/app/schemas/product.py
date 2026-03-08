"""Product request/response schemas."""

import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


class ProductCreate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    price_amount: Decimal = Field(..., ge=0, decimal_places=3)
    currency: str | None = Field(None, min_length=3, max_length=3)
    is_active: bool = True
    sort_order: int = 0
    metadata: dict | None = None
    track_inventory: bool = True
    stock_qty: int | None = Field(None, ge=0)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v is not None and not CURRENCY_PATTERN.match(v):
            raise ValueError("Currency must be a 3-letter uppercase ISO 4217 code")
        return v

    @model_validator(mode="after")
    def default_stock_qty(self) -> "ProductCreate":
        if self.track_inventory and self.stock_qty is None:
            self.stock_qty = 0
        return self


class ProductUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    price_amount: Decimal | None = Field(None, ge=0, decimal_places=3)
    currency: str | None = Field(None, min_length=3, max_length=3)
    is_active: bool | None = None
    sort_order: int | None = None
    metadata: dict | None = None
    track_inventory: bool | None = None
    stock_qty: int | None = Field(None, ge=0)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v is not None and not CURRENCY_PATTERN.match(v):
            raise ValueError("Currency must be a 3-letter uppercase ISO 4217 code")
        return v


class ProductResponse(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID | None = None
    name: str
    description: str | None = None
    price_amount: Decimal
    currency: str | None = None
    effective_currency: str
    is_active: bool
    sort_order: int
    metadata: dict | None = None
    track_inventory: bool
    stock_qty: int | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RestockRequest(BaseModel):
    qty: int = Field(..., gt=0, description="Positive quantity to add to stock")
    note: str | None = Field(None, max_length=500)


class StockMovementResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    delta_qty: int
    reason: str
    note: str | None = None
    order_id: uuid.UUID | None = None
    actor_user_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PublicProductResponse(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID | None = None
    name: str
    description: str | None = None
    price_amount: Decimal
    effective_currency: str
    sort_order: int
    metadata: dict | None = None
    image_url: str | None = None
    in_stock: bool
    stock_display: str | None = None

    model_config = {"from_attributes": True}
