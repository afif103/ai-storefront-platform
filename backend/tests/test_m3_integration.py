"""M3 end-to-end integration tests: public submits, utm_events, admin transitions."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.order import Order
from app.models.utm_event import UtmEvent
from tests.conftest import auth_headers

pytestmark = pytest.mark.m3


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _setup_tenant_product_visit(
    client: AsyncClient,
) -> tuple[dict, str, str, str, str]:
    """Create tenant + product + visit.

    Return (headers, slug, product_id, visit_id, tenant_id).
    """
    uid = _uid()
    sub = f"m3-{uid}"
    email = f"m3-{uid}@test.com"
    slug = f"m3-{uid}"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    # Create tenant
    r = await client.post(
        "/api/v1/tenants/", json={"name": f"M3 {uid}", "slug": slug}, headers=headers
    )
    assert r.status_code == 201
    tenant_id = r.json()["id"]

    # Create product
    r = await client.post(
        "/api/v1/tenants/me/products",
        json={
            "name": f"Widget-{uid}",
            "price_amount": "5.250",
            "is_active": True,
            "stock_qty": 100,
        },
        headers=headers,
    )
    assert r.status_code == 201
    product_id = r.json()["id"]

    # Create visit
    r = await client.post(f"/api/v1/storefront/{slug}/visit", json={"session_id": f"sess-{uid}"})
    assert r.status_code == 201
    visit_id = r.json()["visit_id"]

    return headers, slug, product_id, visit_id, tenant_id


# ---------------------------------------------------------------------------
# Public submission tests
# ---------------------------------------------------------------------------


async def test_donation_submit(client: AsyncClient):
    """POST /storefront/{slug}/donations creates donation with DON-00001."""
    headers, slug, _pid, visit_id, _tid = await _setup_tenant_product_visit(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/donations",
        json={
            "donor_name": "Fatima",
            "donor_phone": "+96598765432",
            "amount": "10.000",
            "currency": "KWD",
            "campaign": "Ramadan 2026",
            "receipt_requested": True,
            "visit_id": visit_id,
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["donation_number"] == "DON-00001"
    assert data["status"] == "pending"
    assert data["amount"] == "10.000"
    assert data["currency"] == "KWD"


async def test_pledge_submit(client: AsyncClient):
    """POST /storefront/{slug}/pledges creates pledge with PLG-00001."""
    headers, slug, _pid, visit_id, _tid = await _setup_tenant_product_visit(client)

    target = (datetime.now(UTC).date() + timedelta(days=30)).isoformat()
    r = await client.post(
        f"/api/v1/storefront/{slug}/pledges",
        json={
            "pledgor_name": "Ali",
            "pledgor_phone": "+96555555555",
            "amount": "100.000",
            "currency": "KWD",
            "target_date": target,
            "visit_id": visit_id,
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["pledge_number"] == "PLG-00001"
    assert data["status"] == "pledged"
    assert data["amount"] == "100.000"


async def test_pledge_past_date_rejected(client: AsyncClient):
    """POST /storefront/{slug}/pledges with past target_date returns 422."""
    headers, slug, _pid, _vid, _tid = await _setup_tenant_product_visit(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/pledges",
        json={
            "pledgor_name": "Bad",
            "amount": "1.000",
            "target_date": "2020-01-01",
        },
    )
    assert r.status_code == 422


async def test_order_submit(client: AsyncClient):
    """POST /storefront/{slug}/orders creates order with ORD-00001 and correct total."""
    headers, slug, product_id, visit_id, _tid = await _setup_tenant_product_visit(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Ahmad",
            "customer_phone": "+96512345678",
            "items": [{"catalog_item_id": product_id, "qty": 2}],
            "payment_notes": "Bank transfer",
            "visit_id": visit_id,
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["order_number"] == "ORD-00001"
    assert data["status"] == "pending"
    assert data["total_amount"] == "10.500"
    assert data["currency"] == "KWD"


async def test_order_invalid_product_rejected(client: AsyncClient):
    """POST /storefront/{slug}/orders with unknown product returns 422."""
    headers, slug, _pid, _vid, _tid = await _setup_tenant_product_visit(client)

    fake_id = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Test",
            "items": [{"catalog_item_id": fake_id, "qty": 1}],
        },
    )
    assert r.status_code == 422
    assert fake_id in r.json()["detail"]


async def test_order_number_increments(client: AsyncClient):
    """Second order for same tenant gets ORD-00002."""
    headers, slug, product_id, _vid, _tid = await _setup_tenant_product_visit(client)

    r1 = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "First",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r1.status_code == 201
    assert r1.json()["order_number"] == "ORD-00001"

    r2 = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Second",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r2.status_code == 201
    assert r2.json()["order_number"] == "ORD-00002"


# ---------------------------------------------------------------------------
# UTM events validation
# ---------------------------------------------------------------------------


async def test_utm_events_created(client: AsyncClient, db: AsyncSession):
    """Submitting order+donation+pledge with visit_id creates 3 utm_events."""
    headers, slug, product_id, visit_id, tenant_id = await _setup_tenant_product_visit(client)

    target = (datetime.now(UTC).date() + timedelta(days=30)).isoformat()

    # Submit all three with same visit_id
    r_don = await client.post(
        f"/api/v1/storefront/{slug}/donations",
        json={"donor_name": "D", "amount": "5.000", "visit_id": visit_id},
    )
    assert r_don.status_code == 201
    don_id = r_don.json()["id"]

    r_plg = await client.post(
        f"/api/v1/storefront/{slug}/pledges",
        json={
            "pledgor_name": "P",
            "amount": "50.000",
            "target_date": target,
            "visit_id": visit_id,
        },
    )
    assert r_plg.status_code == 201
    plg_id = r_plg.json()["id"]

    r_ord = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "O",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
            "visit_id": visit_id,
        },
    )
    assert r_ord.status_code == 201
    ord_id = r_ord.json()["id"]

    # Query utm_events for this visit
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    # Use superuser db — RLS bypassed. Filter by visit_id directly.
    result = await db.execute(select(UtmEvent).where(UtmEvent.visit_id == uuid.UUID(visit_id)))
    events = list(result.scalars().all())

    assert len(events) == 3

    event_map = {str(e.event_ref_id): e.event_type for e in events}
    assert event_map[don_id] == "donation"
    assert event_map[plg_id] == "pledge"
    assert event_map[ord_id] == "order"


async def test_visit_id_invalid_rejected(client: AsyncClient):
    """Submitting with a non-existent visit_id returns 422."""
    headers, slug, product_id, _vid, _tid = await _setup_tenant_product_visit(client)

    fake_visit = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/storefront/{slug}/donations",
        json={"donor_name": "X", "amount": "1.000", "visit_id": fake_visit},
    )
    assert r.status_code == 422
    assert "visit_id" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Admin status transitions
# ---------------------------------------------------------------------------


async def test_order_transition_valid(client: AsyncClient):
    """Admin can transition order pending->confirmed->fulfilled."""
    headers, slug, product_id, _vid, _tid = await _setup_tenant_product_visit(client)

    # Create order
    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Trans",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201
    order_id = r.json()["id"]

    # pending -> confirmed
    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"
    assert r.json()["updated_at"] is not None

    # confirmed -> fulfilled
    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "fulfilled"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "fulfilled"


async def test_order_transition_invalid_422(client: AsyncClient):
    """Invalid transition pending->fulfilled returns 422 with allowed list."""
    headers, slug, product_id, _vid, _tid = await _setup_tenant_product_visit(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Invalid",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201
    order_id = r.json()["id"]

    # pending -> fulfilled (invalid, must go through confirmed)
    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "fulfilled"},
        headers=headers,
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "allowed" in detail
    assert "confirmed" in detail["allowed"]
    assert "cancelled" in detail["allowed"]
    assert "fulfilled" not in detail["allowed"]


async def test_donation_transition_valid(client: AsyncClient):
    """Admin can transition donation pending->received->receipted."""
    headers, slug, _pid, _vid, _tid = await _setup_tenant_product_visit(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/donations",
        json={"donor_name": "DonTrans", "amount": "25.000"},
    )
    assert r.status_code == 201
    don_id = r.json()["id"]

    r = await client.patch(
        f"/api/v1/tenants/me/donations/{don_id}/status",
        json={"status": "received"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "received"

    r = await client.patch(
        f"/api/v1/tenants/me/donations/{don_id}/status",
        json={"status": "receipted"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "receipted"


async def test_pledge_transition_valid(client: AsyncClient):
    """Admin can transition pledge pledged->partially_fulfilled->fulfilled."""
    headers, slug, _pid, _vid, _tid = await _setup_tenant_product_visit(client)

    target = (datetime.now(UTC).date() + timedelta(days=60)).isoformat()
    r = await client.post(
        f"/api/v1/storefront/{slug}/pledges",
        json={"pledgor_name": "PlgTrans", "amount": "200.000", "target_date": target},
    )
    assert r.status_code == 201
    plg_id = r.json()["id"]

    r = await client.patch(
        f"/api/v1/tenants/me/pledges/{plg_id}/status",
        json={"status": "partially_fulfilled"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "partially_fulfilled"

    r = await client.patch(
        f"/api/v1/tenants/me/pledges/{plg_id}/status",
        json={"status": "fulfilled"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "fulfilled"


async def test_cancellation_transitions(client: AsyncClient):
    """Orders and donations can be cancelled from pending; pledges can lapse."""
    headers, slug, product_id, _vid, _tid = await _setup_tenant_product_visit(client)

    # Cancel order
    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Cancel",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    order_id = r.json()["id"]
    r = await client.patch(
        f"/api/v1/tenants/me/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    # Cancel donation
    r = await client.post(
        f"/api/v1/storefront/{slug}/donations",
        json={"donor_name": "Cancel", "amount": "1.000"},
    )
    don_id = r.json()["id"]
    r = await client.patch(
        f"/api/v1/tenants/me/donations/{don_id}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    # Lapse pledge
    target = (datetime.now(UTC).date() + timedelta(days=30)).isoformat()
    r = await client.post(
        f"/api/v1/storefront/{slug}/pledges",
        json={"pledgor_name": "Lapse", "amount": "10.000", "target_date": target},
    )
    plg_id = r.json()["id"]
    r = await client.patch(
        f"/api/v1/tenants/me/pledges/{plg_id}/status",
        json={"status": "lapsed"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "lapsed"


# ---------------------------------------------------------------------------
# Order detail endpoint (M11.6)
# ---------------------------------------------------------------------------


async def test_order_detail_happy_path(client: AsyncClient):
    # GET /tenants/me/orders/{id} returns correct order for the owning tenant.
    headers, slug, product_id, _visit, _ = await _setup_tenant_product_visit(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Detail Test",
            "items": [{"catalog_item_id": product_id, "qty": 2}],
        },
    )
    assert r.status_code == 201
    order_id = r.json()["id"]

    r = await client.get(f"/api/v1/tenants/me/orders/{order_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == order_id
    assert data["customer_name"] == "Detail Test"
    assert data["order_number"].startswith("ORD-")
    assert data["status"] == "pending"
    assert data["source"] == "storefront"


async def test_order_detail_includes_items_and_payment_fields(client: AsyncClient):
    # Response includes JSONB items and payment_method / payment_notes.
    headers, slug, product_id, _visit, _ = await _setup_tenant_product_visit(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Payment Test",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
            "payment_method": "knet",
            "payment_notes": "Please use ref 123",
        },
    )
    assert r.status_code == 201
    order_id = r.json()["id"]

    r = await client.get(f"/api/v1/tenants/me/orders/{order_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["payment_method"] == "knet"
    assert data["payment_notes"] == "Please use ref 123"
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert "name" in item
    assert "qty" in item
    assert "unit_price" in item
    assert "subtotal" in item


async def test_order_detail_cross_tenant_404(client: AsyncClient):
    # Tenant B cannot fetch Tenant A's order.
    _headers_a, slug_a, product_a, _, _ = await _setup_tenant_product_visit(client)
    headers_b, _, _, _, _ = await _setup_tenant_product_visit(client)

    r = await client.post(
        f"/api/v1/storefront/{slug_a}/orders",
        json={
            "customer_name": "Tenant A Customer",
            "items": [{"catalog_item_id": product_a, "qty": 1}],
        },
    )
    assert r.status_code == 201
    order_id = r.json()["id"]

    r = await client.get(f"/api/v1/tenants/me/orders/{order_id}", headers=headers_b)
    assert r.status_code == 404


async def test_order_detail_missing_404(client: AsyncClient):
    # Random UUID returns 404.
    headers, _, _, _, _ = await _setup_tenant_product_visit(client)

    r = await client.get(
        f"/api/v1/tenants/me/orders/{uuid.uuid4()}",
        headers=headers,
    )
    assert r.status_code == 404


async def test_orders_export_not_shadowed_by_detail_route(client: AsyncClient):
    # GET /orders/export returns CSV, not captured by /orders/{order_id}.
    headers, _, _, _, _ = await _setup_tenant_product_visit(client)

    r = await client.get("/api/v1/tenants/me/orders/export", headers=headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# Customer linking on order create (M11.8)
# ---------------------------------------------------------------------------


async def test_storefront_order_with_email_creates_and_links_customer(
    client: AsyncClient, db: AsyncSession
):
    # Storefront order with email creates a customer and sets orders.customer_id.
    _headers, slug, product_id, _vid, tenant_id = await _setup_tenant_product_visit(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "Ahmad",
            "customer_email": "ahmad@example.com",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201
    order_id = r.json()["id"]

    result = await db.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
    order = result.scalar_one()
    assert order.customer_id is not None

    result = await db.execute(select(Customer).where(Customer.id == order.customer_id))
    customer = result.scalar_one()
    assert customer.email == "ahmad@example.com"
    assert customer.tenant_id == uuid.UUID(tenant_id)


async def test_storefront_repeat_email_links_same_customer(client: AsyncClient, db: AsyncSession):
    # Second order with the same email links the existing customer (count stays 1).
    _headers, slug, product_id, _vid, tenant_id = await _setup_tenant_product_visit(client)
    tid = uuid.UUID(tenant_id)

    async def _submit(name: str) -> str:
        r = await client.post(
            f"/api/v1/storefront/{slug}/orders",
            json={
                "customer_name": name,
                "customer_email": "repeat@example.com",
                "items": [{"catalog_item_id": product_id, "qty": 1}],
            },
        )
        assert r.status_code == 201
        return r.json()["id"]

    first_id = await _submit("First")
    second_id = await _submit("Second")

    result = await db.execute(select(Order).where(Order.id == uuid.UUID(first_id)))
    first = result.scalar_one()
    result = await db.execute(select(Order).where(Order.id == uuid.UUID(second_id)))
    second = result.scalar_one()
    assert first.customer_id is not None
    assert first.customer_id == second.customer_id

    result = await db.execute(
        select(func.count()).select_from(Customer).where(Customer.tenant_id == tid)
    )
    assert result.scalar_one() == 1


async def test_storefront_repeat_phone_links_same_customer(client: AsyncClient, db: AsyncSession):
    # Second order with the same phone (no email) links the existing customer.
    _headers, slug, product_id, _vid, tenant_id = await _setup_tenant_product_visit(client)
    tid = uuid.UUID(tenant_id)

    async def _submit(name: str) -> str:
        r = await client.post(
            f"/api/v1/storefront/{slug}/orders",
            json={
                "customer_name": name,
                "customer_phone": "+96599998888",
                "items": [{"catalog_item_id": product_id, "qty": 1}],
            },
        )
        assert r.status_code == 201
        return r.json()["id"]

    first_id = await _submit("First")
    second_id = await _submit("Second")

    result = await db.execute(select(Order).where(Order.id == uuid.UUID(first_id)))
    first = result.scalar_one()
    result = await db.execute(select(Order).where(Order.id == uuid.UUID(second_id)))
    second = result.scalar_one()
    assert first.customer_id is not None
    assert first.customer_id == second.customer_id

    result = await db.execute(
        select(func.count()).select_from(Customer).where(Customer.tenant_id == tid)
    )
    assert result.scalar_one() == 1


async def test_storefront_order_without_contact_no_customer(client: AsyncClient, db: AsyncSession):
    # Order with no phone/email creates no customer; customer_id stays NULL.
    _headers, slug, product_id, _vid, tenant_id = await _setup_tenant_product_visit(client)
    tid = uuid.UUID(tenant_id)

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "NoContact",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201
    order_id = r.json()["id"]

    result = await db.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
    order = result.scalar_one()
    assert order.customer_id is None

    result = await db.execute(
        select(func.count()).select_from(Customer).where(Customer.tenant_id == tid)
    )
    assert result.scalar_one() == 0


async def test_storefront_same_email_distinct_per_tenant(client: AsyncClient, db: AsyncSession):
    # Same email across two tenants creates two distinct, tenant-scoped customers.
    _ha, slug_a, prod_a, _va, tenant_a = await _setup_tenant_product_visit(client)
    _hb, slug_b, prod_b, _vb, tenant_b = await _setup_tenant_product_visit(client)

    ra = await client.post(
        f"/api/v1/storefront/{slug_a}/orders",
        json={
            "customer_name": "Shared",
            "customer_email": "shared@example.com",
            "items": [{"catalog_item_id": prod_a, "qty": 1}],
        },
    )
    assert ra.status_code == 201
    order_a = ra.json()["id"]

    rb = await client.post(
        f"/api/v1/storefront/{slug_b}/orders",
        json={
            "customer_name": "Shared",
            "customer_email": "shared@example.com",
            "items": [{"catalog_item_id": prod_b, "qty": 1}],
        },
    )
    assert rb.status_code == 201
    order_b = rb.json()["id"]

    result = await db.execute(select(Order).where(Order.id == uuid.UUID(order_a)))
    oa = result.scalar_one()
    result = await db.execute(select(Order).where(Order.id == uuid.UUID(order_b)))
    ob = result.scalar_one()
    assert oa.customer_id is not None
    assert ob.customer_id is not None
    assert oa.customer_id != ob.customer_id

    result = await db.execute(select(Customer).where(Customer.id == oa.customer_id))
    ca = result.scalar_one()
    result = await db.execute(select(Customer).where(Customer.id == ob.customer_id))
    cb = result.scalar_one()
    assert ca.tenant_id == uuid.UUID(tenant_a)
    assert cb.tenant_id == uuid.UUID(tenant_b)


# ---------------------------------------------------------------------------
# customer_id exposure in order responses (M11.8 Phase 4)
# ---------------------------------------------------------------------------


async def test_storefront_create_response_includes_customer_id(
    client: AsyncClient, db: AsyncSession
):
    # Storefront create response exposes the linked customer_id (matches persisted row).
    _headers, slug, product_id, _vid, _tid = await _setup_tenant_product_visit(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "RespCid",
            "customer_email": "respcid@example.com",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["customer_id"] is not None

    result = await db.execute(select(Order).where(Order.id == uuid.UUID(body["id"])))
    order = result.scalar_one()
    assert body["customer_id"] == str(order.customer_id)


async def test_storefront_order_detail_response_includes_customer_id(client: AsyncClient):
    # Dashboard order detail response exposes the same customer_id as the create response.
    headers, slug, product_id, _vid, _tid = await _setup_tenant_product_visit(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/orders",
        json={
            "customer_name": "DetailCid",
            "customer_email": "detailcid@example.com",
            "items": [{"catalog_item_id": product_id, "qty": 1}],
        },
    )
    assert r.status_code == 201
    created = r.json()
    assert created["customer_id"] is not None

    r = await client.get(f"/api/v1/tenants/me/orders/{created['id']}", headers=headers)
    assert r.status_code == 200
    detail = r.json()
    assert detail["customer_id"] == created["customer_id"]
