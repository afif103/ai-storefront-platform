"""Storefront config request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.payment import PaymentMethodsConfig
from app.schemas.shipping import ShippingConfig

_HEX_COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


class StorefrontConfigUpdate(BaseModel):
    """PUT body — all fields optional (patch semantics)."""

    logo_s3_key: str | None = None
    primary_color: str | None = Field(None, max_length=7, pattern=_HEX_COLOR_PATTERN)
    secondary_color: str | None = Field(None, max_length=7, pattern=_HEX_COLOR_PATTERN)
    hero_text: str | None = None
    custom_css: dict | None = None
    payment_methods: PaymentMethodsConfig | None = None
    shipping: ShippingConfig | None = None


class StorefrontConfigResponse(BaseModel):
    id: uuid.UUID
    logo_s3_key: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    hero_text: str | None = None
    custom_css: dict | None = None
    payment_methods: PaymentMethodsConfig | None = None
    shipping: ShippingConfig | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
