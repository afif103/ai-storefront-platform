"""Shared helpers for M2 integration tests."""

import uuid

from httpx import AsyncClient

from tests.conftest import auth_headers


async def create_tenant_get_headers(
    client: AsyncClient,
    *,
    slug_prefix: str = "m2",
) -> tuple[dict, str]:
    """Create a tenant via the API and return (auth_headers, slug).

    Uses a unique sub/email per call so each test gets an isolated tenant.
    """
    unique = uuid.uuid4().hex[:8]
    sub = f"{slug_prefix}-sub-{unique}"
    email = f"{slug_prefix}-{unique}@example.com"
    slug = f"{slug_prefix}-{unique}"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    resp = await client.post(
        "/api/v1/tenants/",
        json={"name": f"Test {slug}", "slug": slug},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return headers, slug
