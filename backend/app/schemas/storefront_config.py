"""Storefront config request/response schemas."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class StorefrontConfigUpdate(BaseModel):
    """PUT body — all fields optional (patch semantics)."""

    logo_s3_key: str | None = None
    primary_color: str | None = Field(None, max_length=7)
    secondary_color: str | None = Field(None, max_length=7)
    hero_text: str | None = None
    custom_css: dict | None = None

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def validate_hex_color(cls, v: str | None) -> str | None:
        if v is not None and not _HEX_COLOR_RE.match(v):
            raise ValueError("Must be a hex color in #RRGGBB format")
        return v


class StorefrontConfigResponse(BaseModel):
    id: uuid.UUID
    logo_s3_key: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    hero_text: str | None = None
    custom_css: dict | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
