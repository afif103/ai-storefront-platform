"""Visit capture request/response schemas."""

import uuid

from pydantic import BaseModel, Field


class VisitCreateRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=255)
    landed_path: str | None = Field(None, max_length=2048)
    referrer: str | None = Field(None, max_length=2048)
    utm_source: str | None = Field(None, max_length=255)
    utm_medium: str | None = Field(None, max_length=255)
    utm_campaign: str | None = Field(None, max_length=255)
    utm_content: str | None = Field(None, max_length=255)
    utm_term: str | None = Field(None, max_length=255)


class VisitCreateResponse(BaseModel):
    visit_id: uuid.UUID
