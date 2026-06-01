"""M11.7 customer CRUD endpoint integration tests."""

import uuid

from httpx import AsyncClient

from tests.conftest import auth_headers


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _setup_tenant(client: AsyncClient) -> dict:
    # Create a tenant (owner) and return auth headers with Content-Type.
    uid = _uid()
    headers = auth_headers(sub=f"cust-{uid}", email=f"cust-{uid}@test.com")
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"Cust {uid}", "slug": f"cust-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201
    return headers


async def _invite_member(client: AsyncClient, owner_headers: dict) -> dict:
    # Invite + accept a member; return member headers.
    uid = _uid()
    member_email = f"member-{uid}@test.com"

    r = await client.post(
        "/api/v1/tenants/me/members/invite",
        json={"email": member_email, "role": "member"},
        headers=owner_headers,
    )
    assert r.status_code == 201

    member_headers = auth_headers(sub=f"member-{uid}", email=member_email)
    member_headers["Content-Type"] = "application/json"

    r = await client.post("/api/v1/auth/accept-invite", headers=member_headers)
    assert r.status_code == 200

    return member_headers


async def test_create_customer_happy_path(client: AsyncClient):
    headers = await _setup_tenant(client)

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Alice", "phone": "12345678", "email": "alice@example.com"},
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Alice"
    assert data["phone"] == "12345678"
    assert data["email"] == "alice@example.com"
    assert "id" in data
    assert "tenant_id" not in data


async def test_list_customers_returns_tenant_customers(client: AsyncClient):
    headers = await _setup_tenant(client)

    for name in ("Alice", "Bob"):
        r = await client.post(
            "/api/v1/tenants/me/customers",
            json={"name": name},
            headers=headers,
        )
        assert r.status_code == 201

    r = await client.get("/api/v1/tenants/me/customers", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "next_cursor" in data
    assert "has_more" in data
    assert len(data["items"]) == 2


async def test_get_customer_by_id(client: AsyncClient):
    headers = await _setup_tenant(client)

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Alice"},
        headers=headers,
    )
    customer_id = r.json()["id"]

    r = await client.get(f"/api/v1/tenants/me/customers/{customer_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == customer_id


async def test_update_customer(client: AsyncClient):
    headers = await _setup_tenant(client)

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Alice"},
        headers=headers,
    )
    customer_id = r.json()["id"]

    r = await client.patch(
        f"/api/v1/tenants/me/customers/{customer_id}",
        json={"name": "Alice Updated", "notes": "VIP"},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Alice Updated"
    assert data["notes"] == "VIP"


async def test_duplicate_phone_within_tenant_returns_409(client: AsyncClient):
    headers = await _setup_tenant(client)

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Alice", "phone": "12345678"},
        headers=headers,
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Bob", "phone": "12345678"},
        headers=headers,
    )
    assert r.status_code == 409


async def test_duplicate_email_within_tenant_returns_409(client: AsyncClient):
    headers = await _setup_tenant(client)

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Alice", "email": "dup@example.com"},
        headers=headers,
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Bob", "email": "dup@example.com"},
        headers=headers,
    )
    assert r.status_code == 409


async def test_same_phone_email_across_tenants_allowed(client: AsyncClient):
    headers_a = await _setup_tenant(client)
    headers_b = await _setup_tenant(client)

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Alice", "phone": "12345678", "email": "shared@example.com"},
        headers=headers_a,
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Alice", "phone": "12345678", "email": "shared@example.com"},
        headers=headers_b,
    )
    assert r.status_code == 201


async def test_cross_tenant_get_returns_404(client: AsyncClient):
    headers_a = await _setup_tenant(client)
    headers_b = await _setup_tenant(client)

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Alice"},
        headers=headers_a,
    )
    customer_id = r.json()["id"]

    r = await client.get(f"/api/v1/tenants/me/customers/{customer_id}", headers=headers_b)
    assert r.status_code == 404


async def test_cross_tenant_patch_returns_404(client: AsyncClient):
    headers_a = await _setup_tenant(client)
    headers_b = await _setup_tenant(client)

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Alice"},
        headers=headers_a,
    )
    customer_id = r.json()["id"]

    r = await client.patch(
        f"/api/v1/tenants/me/customers/{customer_id}",
        json={"name": "Hacked"},
        headers=headers_b,
    )
    assert r.status_code == 404


async def test_delete_then_get_returns_404(client: AsyncClient):
    headers = await _setup_tenant(client)

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Alice"},
        headers=headers,
    )
    customer_id = r.json()["id"]

    r = await client.delete(f"/api/v1/tenants/me/customers/{customer_id}", headers=headers)
    assert r.status_code == 204

    r = await client.get(f"/api/v1/tenants/me/customers/{customer_id}", headers=headers)
    assert r.status_code == 404


async def test_whitespace_only_name_returns_422(client: AsyncClient):
    headers = await _setup_tenant(client)

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "   "},
        headers=headers,
    )
    assert r.status_code == 422


async def test_email_lowercased_on_response(client: AsyncClient):
    headers = await _setup_tenant(client)

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Alice", "email": "ALICE@EXAMPLE.COM"},
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["email"] == "alice@example.com"


async def test_member_can_list_but_cannot_create(client: AsyncClient):
    owner_headers = await _setup_tenant(client)
    member_headers = await _invite_member(client, owner_headers)

    r = await client.get("/api/v1/tenants/me/customers", headers=member_headers)
    assert r.status_code == 200

    r = await client.post(
        "/api/v1/tenants/me/customers",
        json={"name": "Alice"},
        headers=member_headers,
    )
    assert r.status_code == 403
