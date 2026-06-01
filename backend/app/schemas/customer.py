"""Customer request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _normalize_optional(v: str | None) -> str | None:
    if v is None:
        return None
    stripped = v.strip()
    return stripped if stripped else None


def _normalize_email(v: str | None) -> str | None:
    if v is None:
        return None
    stripped = v.strip().lower()
    return stripped if stripped else None


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, max_length=2000)

    @field_validator("name", mode="before")
    @classmethod
    def _trim_name(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @field_validator("phone", "notes", mode="before")
    @classmethod
    def _normalize_optional_fields(cls, v: str | None) -> str | None:
        return _normalize_optional(v)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email_field(cls, v: str | None) -> str | None:
        return _normalize_email(v)


class CustomerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, max_length=2000)

    @field_validator("name", mode="before")
    @classmethod
    def _trim_name(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    @field_validator("phone", "notes", mode="before")
    @classmethod
    def _normalize_optional_fields(cls, v: str | None) -> str | None:
        return _normalize_optional(v)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email_field(cls, v: str | None) -> str | None:
        return _normalize_email(v)


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None
    email: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}
