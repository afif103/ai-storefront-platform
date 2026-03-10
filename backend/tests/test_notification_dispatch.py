"""M7 P3 — Notification dispatch wiring integration tests."""

import uuid
from unittest.mock import patch, MagicMock

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.m7


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _setup_tenant_with_product(client: AsyncClient) -> tuple[dict, str, str]:
    """Create tenant + product. Return (headers, slug, product_id)."""
    uid = _uid()
    sub = f"nd-{uid}"
    email = f"nd-{uid}@test.com"
    slug = f"nd-{uid}"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"ND Tenant {uid}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/tenants/me/products",
        json={"name": f"Widget-{uid}", "price_amount": "5.000", "is_active": True, "track_inventory": False},
        headers=headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]

    return headers, slug, product_id


# ---- Order dispatch ----


@patch("app.api.v1.public_storefront.send_order_notification")
async def test_order_creation_dispatches_notification(
    mock_task: MagicMock, client: AsyncClient
):
    """Order creation calls send_order_notification.delay with correct args."""
    headers, slug, product_id = await _setup_tenant_with_product(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Alice",
            "customer_email": "alice@test.com",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201
    order_id = r.json()["id"]

    mock_task.delay.assert_called_once()
    call_args = mock_task.delay.call_args[0]
    assert call_args[1] == order_id  # second arg is order_id


# ---- Donation dispatch ----


@patch("app.api.v1.public_storefront.send_donation_notification")
async def test_donation_creation_dispatches_notification(
    mock_task: MagicMock, client: AsyncClient
):
    """Donation creation calls send_donation_notification.delay with correct args."""
    headers, slug, _ = await _setup_tenant_with_product(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/donations",
        json={
            "donor_name": "Bob",
            "amount": "10.000",
            "currency": "KWD",
        },
    )
    assert r.status_code == 201
    donation_id = r.json()["id"]

    mock_task.delay.assert_called_once()
    call_args = mock_task.delay.call_args[0]
    assert call_args[1] == donation_id  # second arg is donation_id


# ---- Resilience: .delay() failure does not break the endpoint ----


@patch("app.api.v1.public_storefront.send_order_notification")
async def test_order_creation_succeeds_when_delay_raises(
    mock_task: MagicMock, client: AsyncClient
):
    """If .delay() raises, the order is still created and 201 returned."""
    mock_task.delay.side_effect = RuntimeError("Redis down")

    headers, slug, product_id = await _setup_tenant_with_product(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Carol",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201
    assert r.json()["order_number"] is not None


@patch("app.api.v1.public_storefront.send_donation_notification")
async def test_donation_creation_succeeds_when_delay_raises(
    mock_task: MagicMock, client: AsyncClient
):
    """If .delay() raises, the donation is still created and 201 returned."""
    mock_task.delay.side_effect = RuntimeError("Redis down")

    headers, slug, _ = await _setup_tenant_with_product(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/donations",
        json={
            "donor_name": "Dave",
            "amount": "5.000",
            "currency": "KWD",
        },
    )
    assert r.status_code == 201
    assert r.json()["donation_number"] is not None
