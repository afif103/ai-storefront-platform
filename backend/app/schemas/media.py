"""Media upload/download request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.services.storage import ALLOWED_CONTENT_TYPES, MAX_UPLOAD_SIZE


class MediaUploadRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1)
    size_bytes: int = Field(..., gt=0, le=MAX_UPLOAD_SIZE)
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _entity_fields_paired(self) -> "MediaUploadRequest":
        has_type = self.entity_type is not None
        has_id = self.entity_id is not None
        if has_type != has_id:
            raise ValueError("entity_type and entity_id must both be provided or both omitted")
        return self

    def validate_content_type(self) -> None:
        if self.content_type not in ALLOWED_CONTENT_TYPES:
            allowed = ", ".join(sorted(ALLOWED_CONTENT_TYPES))
            raise ValueError(f"content_type must be one of: {allowed}")


class MediaUploadResponse(BaseModel):
    media_id: uuid.UUID
    upload_url: str
    s3_key: str
    expires_in: int


class MediaAssetResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID | None = None
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    s3_key: str
    file_name: str | None = None
    content_type: str | None = None
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaDownloadResponse(BaseModel):
    download_url: str
    expires_in: int
