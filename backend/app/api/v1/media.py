"""Presigned media upload/download endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_with_tenant, require_role
from app.models.media_asset import MediaAsset
from app.models.user import User
from app.schemas.media import (
    MediaDownloadResponse,
    MediaUploadRequest,
    MediaUploadResponse,
)
from app.services.storage import (
    ALLOWED_CONTENT_TYPES,
    PRESIGN_DOWNLOAD_EXPIRES,
    PRESIGN_UPLOAD_EXPIRES,
    build_tenant_key,
    presign_get,
    presign_put,
)

router = APIRouter()


@router.post("/upload-url", response_model=MediaUploadResponse, status_code=201)
async def create_upload_url(
    body: MediaUploadRequest,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
):
    """Generate a presigned PUT URL for uploading a file to S3.

    Creates a media_assets row and returns the upload URL.
    The client should PUT the file directly to the returned URL.
    """
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    # Validate content type
    if body.content_type not in ALLOWED_CONTENT_TYPES:
        allowed = ", ".join(sorted(ALLOWED_CONTENT_TYPES))
        raise HTTPException(
            status_code=400,
            detail=f"content_type must be one of: {allowed}",
        )

    # Build tenant-scoped S3 key
    s3_key = build_tenant_key(tenant_id, body.file_name)

    # Create media_assets row
    media = MediaAsset(
        tenant_id=tenant_id,
        product_id=body.product_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        s3_key=s3_key,
        file_name=body.file_name,
        content_type=body.content_type,
    )
    db.add(media)
    await db.flush()

    # Generate presigned PUT URL
    upload_url = presign_put(s3_key, body.content_type)

    return MediaUploadResponse(
        media_id=media.id,
        upload_url=upload_url,
        s3_key=s3_key,
        expires_in=PRESIGN_UPLOAD_EXPIRES,
    )


@router.get("/{media_id}/download-url", response_model=MediaDownloadResponse)
async def get_download_url(
    media_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
):
    """Generate a presigned GET URL for downloading a media file.

    RLS ensures only the current tenant's assets are visible.
    """
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    result = await db.execute(select(MediaAsset).where(MediaAsset.id == media_id))
    media = result.scalar_one_or_none()
    if media is None:
        raise HTTPException(status_code=404, detail="Media asset not found")

    download_url = presign_get(media.s3_key)

    return MediaDownloadResponse(
        download_url=download_url,
        expires_in=PRESIGN_DOWNLOAD_EXPIRES,
    )
