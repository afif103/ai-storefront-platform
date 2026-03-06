"""Test that status transitions create audit_events rows."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from tests.conftest import auth_headers

pytestmark = pytest.mark.m3


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def test_order_transition_creates_audit_event(
    client: AsyncClient, db: AsyncSession
):
    """PATCH order status creates an audit_events row."""
    uid = _uid()
    sub = f"aud-{uid}"
    email = f"aud-{uid}@test.com"
    slug = f"aud-{uid}"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    # Create tenant
    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"Audit {uid}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201
    tenant_id = r.json()["id"]

    # Create product
    r = await client.post(
        "/api/v1/tenants/me/products",
        json={"name": f"AudProd-{uid}", "price_amount": "1.000", "is_active": True, "stock_qty": 100},
        headers=headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]

    # Submit order
    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "AuditTest",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201
    order_id = r.json()["id"]

    # Transition: pending -> confirmed
    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert r.status_code == 200

    # Verify audit_events row was created
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    result = await db.execute(
        select(AuditEvent).where(
            AuditEvent.entity_type == "order",
            AuditEvent.entity_id == uuid.UUID(order_id),
        )
    )
    events = list(result.scalars().all())

    assert len(events) == 1
    event = events[0]
    assert event.action == "status_transition"
    assert event.from_status == "pending"
    assert event.to_status == "confirmed"
    assert event.tenant_id == uuid.UUID(tenant_id)
