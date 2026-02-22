"""Media upload/download request/response schemas."""

import uuid

from pydantic import BaseModel, Field

from app.services.storage import ALLOWED_CONTENT_TYPES, MAX_UPLOAD_SIZE


class MediaUploadRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1)
    size_bytes: int = Field(..., gt=0, le=MAX_UPLOAD_SIZE)
    entity_type: str = Field("product")
    entity_id: uuid.UUID
    product_id: uuid.UUID | None = None

    def validate_content_type(self) -> None:
        if self.content_type not in ALLOWED_CONTENT_TYPES:
            allowed = ", ".join(sorted(ALLOWED_CONTENT_TYPES))
            raise ValueError(f"content_type must be one of: {allowed}")


class MediaUploadResponse(BaseModel):
    media_id: uuid.UUID
    upload_url: str
    s3_key: str
    expires_in: int


class MediaDownloadResponse(BaseModel):
    download_url: str
    expires_in: int
