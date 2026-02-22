"""M2 integration tests: presigned media upload/download endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from tests.m2_helpers import create_tenant_get_headers

pytestmark = pytest.mark.m2


async def test_upload_url_success(client: AsyncClient):
    """POST /tenants/me/media/upload-url creates media row and returns presigned URL."""
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="media-up")

    body = {
        "file_name": "photo.jpg",
        "content_type": "image/jpeg",
        "size_bytes": 1024,
        "entity_type": "product",
        "entity_id": str(uuid.uuid4()),
    }
    resp = await client.post("/api/v1/tenants/me/media/upload-url", json=body, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "media_id" in data
    assert "upload_url" in data
    assert "s3_key" in data
    assert data["expires_in"] == 900
    # S3 key must start with tenant prefix (UUID format)
    assert "/" in data["s3_key"]


async def test_upload_url_no_entity(client: AsyncClient):
    """POST /tenants/me/media/upload-url succeeds without entity fields (e.g. logo)."""
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="media-ne")

    body = {
        "file_name": "logo.png",
        "content_type": "image/png",
        "size_bytes": 2048,
    }
    resp = await client.post("/api/v1/tenants/me/media/upload-url", json=body, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "media_id" in data
    assert "upload_url" in data


async def test_upload_url_rejects_bad_content_type(client: AsyncClient):
    """POST /tenants/me/media/upload-url rejects unsupported content types."""
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="media-ct")

    body = {
        "file_name": "script.js",
        "content_type": "application/javascript",
        "size_bytes": 512,
        "entity_type": "product",
        "entity_id": str(uuid.uuid4()),
    }
    resp = await client.post("/api/v1/tenants/me/media/upload-url", json=body, headers=headers)
    assert resp.status_code == 400
    assert "content_type" in resp.json()["detail"]


async def test_upload_url_rejects_oversized(client: AsyncClient):
    """POST /tenants/me/media/upload-url rejects files exceeding 10 MB."""
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="media-sz")

    body = {
        "file_name": "huge.png",
        "content_type": "image/png",
        "size_bytes": 20 * 1024 * 1024,  # 20 MB
        "entity_type": "product",
        "entity_id": str(uuid.uuid4()),
    }
    resp = await client.post("/api/v1/tenants/me/media/upload-url", json=body, headers=headers)
    assert resp.status_code == 422  # Pydantic validation: le=10MB


async def test_upload_url_unauthenticated(client: AsyncClient):
    """POST /tenants/me/media/upload-url without auth returns 401."""
    body = {
        "file_name": "photo.jpg",
        "content_type": "image/jpeg",
        "size_bytes": 1024,
        "entity_type": "product",
        "entity_id": str(uuid.uuid4()),
    }
    resp = await client.post("/api/v1/tenants/me/media/upload-url", json=body)
    assert resp.status_code == 401


async def test_download_url_success(client: AsyncClient):
    """GET /tenants/me/media/{id}/download-url returns presigned GET URL."""
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="media-dl")

    # First create a media asset via upload
    upload_body = {
        "file_name": "doc.pdf",
        "content_type": "application/pdf",
        "size_bytes": 2048,
        "entity_type": "product",
        "entity_id": str(uuid.uuid4()),
    }
    upload_resp = await client.post(
        "/api/v1/tenants/me/media/upload-url", json=upload_body, headers=headers
    )
    assert upload_resp.status_code == 201
    media_id = upload_resp.json()["media_id"]

    # Download URL
    dl_resp = await client.get(
        f"/api/v1/tenants/me/media/{media_id}/download-url", headers=headers
    )
    assert dl_resp.status_code == 200
    data = dl_resp.json()
    assert "download_url" in data
    assert data["expires_in"] == 900


async def test_download_url_not_found(client: AsyncClient):
    """GET /tenants/me/media/{id}/download-url returns 404 for unknown ID."""
    headers, _slug = await create_tenant_get_headers(client, slug_prefix="media-nf")
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/tenants/me/media/{fake_id}/download-url", headers=headers)
    assert resp.status_code == 404
