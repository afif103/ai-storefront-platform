"""S3 / MinIO presigned-URL helpers.

All keys MUST start with ``{tenant_id}/`` — this is enforced in
``build_tenant_key`` and never accepted from the client.
"""

import logging
import os
import uuid
from urllib.parse import quote, urlparse, urlunparse

import boto3
from botocore.config import Config

from app.core.config import settings

logger = logging.getLogger(__name__)

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


_minio_cred_warned = False


def _get_s3_client():  # type: ignore[no-untyped-def]
    global _minio_cred_warned  # noqa: PLW0603
    config_kwargs: dict = {"signature_version": "s3v4"}
    if settings.S3_ENDPOINT_URL:
        config_kwargs["s3"] = {"addressing_style": "path"}
    kwargs: dict = {
        "service_name": "s3",
        "region_name": settings.AWS_REGION,
        "config": Config(**config_kwargs),
    }
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

    # Warn if MinIO endpoint is set but boto3 will pick up real AWS creds
    if settings.S3_ENDPOINT_URL and not _minio_cred_warned:
        env_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        if env_key.startswith("AKIA") and (
            not settings.AWS_ACCESS_KEY_ID or settings.AWS_ACCESS_KEY_ID.startswith("AKIA")
        ):
            logger.warning(
                "S3_ENDPOINT_URL points to MinIO but AWS_ACCESS_KEY_ID "
                "looks like a real AWS key (AKIA...). Presigned URLs will "
                "be signed with AWS creds and fail against MinIO. "
                "Clear AWS_* env vars or set them to minioadmin in .env."
            )
        _minio_cred_warned = True

    return boto3.client(**kwargs)


def _rewrite_presigned_url(url: str) -> str:
    """Swap scheme+netloc to S3_PUBLIC_ENDPOINT so browsers can reach MinIO."""
    if not settings.S3_PUBLIC_ENDPOINT:
        return url
    public = urlparse(settings.S3_PUBLIC_ENDPOINT)
    parsed = urlparse(url)
    return urlunparse(parsed._replace(scheme=public.scheme, netloc=public.netloc))


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
    url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires,
    )
    return _rewrite_presigned_url(url)


def delete_object(key: str) -> None:
    """Best-effort delete of an S3 object."""
    client = _get_s3_client()
    client.delete_object(Bucket=settings.S3_BUCKET, Key=key)


def presign_get(
    key: str,
    expires: int = PRESIGN_DOWNLOAD_EXPIRES,
) -> str:
    """Generate a presigned GET URL for downloading from S3."""
    client = _get_s3_client()
    url = client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": key,
        },
        ExpiresIn=expires,
    )
    return _rewrite_presigned_url(url)
