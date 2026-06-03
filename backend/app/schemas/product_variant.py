"""Product variant request/response schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


class ProductVariantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    size: str | None = Field(None, max_length=255)
    color: str | None = Field(None, max_length=255)
    sku: str | None = Field(None, max_length=64)
    barcode: str | None = Field(None, max_length=64)
    price_amount: Decimal | None = Field(None, ge=0, decimal_places=3)
    stock_qty: int | None = Field(None, ge=0)
    is_active: bool = True
    sort_order: int = 0

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    @field_validator("size", "color", "sku", "barcode", mode="before")
    @classmethod
    def _normalize_text(cls, v: str | None) -> str | None:
        return _normalize_optional_text(v)


class ProductVariantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    size: str | None = Field(None, max_length=255)
    color: str | None = Field(None, max_length=255)
    sku: str | None = Field(None, max_length=64)
    barcode: str | None = Field(None, max_length=64)
    price_amount: Decimal | None = Field(None, ge=0, decimal_places=3)
    stock_qty: int | None = Field(None, ge=0)
    is_active: bool | None = None
    sort_order: int | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    @field_validator("size", "color", "sku", "barcode", mode="before")
    @classmethod
    def _normalize_text(cls, v: str | None) -> str | None:
        return _normalize_optional_text(v)


class ProductVariantResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    size: str | None = None
    color: str | None = None
    sku: str | None = None
    barcode: str | None = None
    price_amount: Decimal | None = None
    stock_qty: int | None = None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
