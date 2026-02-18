"""Tenant request/response schemas."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=3, max_length=63)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v):
            raise ValueError(
                "Slug must be 3-63 chars, lowercase alphanumeric with hyphens, "
                "cannot start or end with a hyphen"
            )
        return v


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, min_length=3, max_length=63)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None and not SLUG_PATTERN.match(v):
            raise ValueError("Slug must be 3-63 chars, lowercase alphanumeric with hyphens")
        return v
