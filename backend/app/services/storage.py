"""S3 / MinIO presigned-URL helpers.

All keys MUST start with ``{tenant_id}/`` — this is enforced in
``build_tenant_key`` and never accepted from the client.
"""

import uuid
from urllib.parse import quote

import boto3
from botocore.config import Config

from app.core.config import settings

PRESIGN_UPLOAD_EXPIRES = 900  # 15 min
PRESIGN_DOWNLOAD_EXPIRES = 900  # 15 min
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    }
)


def _get_s3_client():  # type: ignore[no-untyped-def]
    kwargs: dict = {
        "service_name": "s3",
        "region_name": settings.AWS_REGION,
        "config": Config(signature_version="s3v4"),
    }
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client(**kwargs)


def build_tenant_key(tenant_id: uuid.UUID, file_name: str) -> str:
    """Build an S3 key scoped to the tenant: ``{tenant_id}/media/{uuid}-{safe_name}``."""
    safe_name = quote(file_name.strip().replace(" ", "_"), safe="._-")
    return f"{tenant_id}/media/{uuid.uuid4()}-{safe_name}"


def presign_put(
    key: str,
    content_type: str,
    expires: int = PRESIGN_UPLOAD_EXPIRES,
) -> str:
    """Generate a presigned PUT URL for uploading to S3."""
    client = _get_s3_client()
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires,
    )


def presign_get(
    key: str,
    expires: int = PRESIGN_DOWNLOAD_EXPIRES,
) -> str:
    """Generate a presigned GET URL for downloading from S3."""
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": key,
        },
        ExpiresIn=expires,
    )
