"""Analytics ingest + dashboard summary integration tests."""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers

pytestmark = pytest.mark.m5


def _summary_qs() -> str:
    """Return query string with a valid date range covering today."""
    today = date.today()
    from_date = today - timedelta(days=7)
    to_date = today + timedelta(days=1)
    return f"from={from_date}&to={to_date}"


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _create_tenant(client: AsyncClient) -> tuple[str, str, dict]:
    """Create tenant, return (slug, tenant_id, auth_headers)."""
    uid = _uid()
    sub = f"analytics-{uid}"
    email = f"analytics-{uid}@test.com"
    headers = auth_headers(sub=sub, email=email)
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"Analytics {uid}", "slug": f"analytics-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["slug"], r.json()["id"], headers


def _ingest_payload(
    visitor_id: str | None = None,
    session_id: str | None = None,
    events: list[dict] | None = None,
    utm_source: str | None = None,
) -> dict:
    return {
        "visitor_id": visitor_id or str(uuid.uuid4()),
        "session_id": session_id or str(uuid.uuid4()),
        "utm_source": utm_source,
        "events": events or [{"name": "storefront_view"}],
    }


async def test_ingest_happy_path(client: AsyncClient, db: AsyncSession):
    """POST /storefront/{slug}/analytics/events inserts visitor, session, events."""
    slug, tenant_id, _headers = await _create_tenant(client)
    visitor_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    payload = _ingest_payload(
        visitor_id=visitor_id,
        session_id=session_id,
        events=[
            {"name": "storefront_view", "props": {"path": "/"}},
            {"name": "product_view", "props": {"product_id": "abc"}},
        ],
        utm_source="google",
    )

    r = await client.post(
        f"/api/v1/storefront/{slug}/analytics/events",
        json=payload,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["accepted"] == 2
    assert data["skipped"] == 0

    # Verify rows in DB (superuser session, set tenant + user context for SELECT)
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    await db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(uuid.uuid4())},
    )

    visitor_row = await db.execute(
        text("SELECT * FROM attribution_visitors " "WHERE tenant_id = :tid AND visitor_id = :vid"),
        {"tid": tenant_id, "vid": visitor_id},
    )
    assert visitor_row.one() is not None

    session_row = await db.execute(
        text("SELECT * FROM attribution_sessions " "WHERE tenant_id = :tid AND session_id = :sid"),
        {"tid": tenant_id, "sid": session_id},
    )
    s = session_row.one()
    assert s.utm_source == "google"

    events_result = await db.execute(
        text(
            "SELECT event_name FROM attribution_events "
            "WHERE tenant_id = :tid AND session_id = :sid "
            "ORDER BY occurred_at"
        ),
        {"tid": tenant_id, "sid": session_id},
    )
    names = [r.event_name for r in events_result.all()]
    assert names == ["storefront_view", "product_view"]


async def test_dedupe_storefront_view(client: AsyncClient):
    """Second storefront_view within 10 min is skipped."""
    slug, _tid, _headers = await _create_tenant(client)
    visitor_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    payload = _ingest_payload(
        visitor_id=visitor_id,
        session_id=session_id,
        events=[{"name": "storefront_view"}],
    )

    # First request — accepted
    r1 = await client.post(f"/api/v1/storefront/{slug}/analytics/events", json=payload)
    assert r1.status_code == 200
    assert r1.json()["accepted"] == 1
    assert r1.json()["skipped"] == 0

    # Second request — storefront_view skipped
    r2 = await client.post(f"/api/v1/storefront/{slug}/analytics/events", json=payload)
    assert r2.status_code == 200
    assert r2.json()["accepted"] == 0
    assert r2.json()["skipped"] == 1


async def test_invalid_event_name_rejected(client: AsyncClient):
    """Unknown event name returns 422."""
    slug, _tid, _headers = await _create_tenant(client)

    payload = _ingest_payload(events=[{"name": "invalid_event"}])

    r = await client.post(f"/api/v1/storefront/{slug}/analytics/events", json=payload)
    assert r.status_code == 422


async def test_summary_is_tenant_scoped(client: AsyncClient):
    """Tenant A cannot see Tenant B's analytics in the summary endpoint."""
    slug_a, _tid_a, headers_a = await _create_tenant(client)
    slug_b, _tid_b, headers_b = await _create_tenant(client)

    # Ingest events for tenant A
    payload_a = _ingest_payload(
        events=[
            {"name": "storefront_view"},
            {"name": "product_view"},
            {"name": "submit_order"},
        ],
    )
    r = await client.post(f"/api/v1/storefront/{slug_a}/analytics/events", json=payload_a)
    assert r.status_code == 200

    # Ingest events for tenant B
    payload_b = _ingest_payload(
        events=[{"name": "storefront_view"}],
    )
    r = await client.post(f"/api/v1/storefront/{slug_b}/analytics/events", json=payload_b)
    assert r.status_code == 200

    # Tenant A summary should see its own events only
    r_a = await client.get(
        f"/api/v1/tenants/me/analytics/summary?{_summary_qs()}",
        headers=headers_a,
    )
    assert r_a.status_code == 200
    data_a = r_a.json()
    assert data_a["event_counts"].get("storefront_view", 0) == 1
    assert data_a["event_counts"].get("submit_order", 0) == 1

    # Tenant B summary should see only its own storefront_view
    r_b = await client.get(
        f"/api/v1/tenants/me/analytics/summary?{_summary_qs()}",
        headers=headers_b,
    )
    assert r_b.status_code == 200
    data_b = r_b.json()
    assert data_b["event_counts"].get("storefront_view", 0) == 1
    assert data_b["event_counts"].get("submit_order", 0) == 0


async def test_summary_correctness(client: AsyncClient):
    """Summary endpoint returns correct counts and funnel rates."""
    slug, _tid, headers = await _create_tenant(client)
    visitor_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    payload = _ingest_payload(
        visitor_id=visitor_id,
        session_id=session_id,
        events=[
            {"name": "storefront_view"},
            {"name": "product_view"},
            {"name": "product_view"},
            {"name": "add_to_cart"},
            {"name": "submit_order"},
        ],
        utm_source="instagram",
    )

    r = await client.post(f"/api/v1/storefront/{slug}/analytics/events", json=payload)
    assert r.status_code == 200
    assert r.json()["accepted"] == 5

    # Query summary
    r_s = await client.get(
        f"/api/v1/tenants/me/analytics/summary?{_summary_qs()}",
        headers=headers,
    )
    assert r_s.status_code == 200
    data = r_s.json()

    assert data["visitors"] == 1
    assert data["sessions"] == 1
    assert data["event_counts"]["storefront_view"] == 1
    assert data["event_counts"]["product_view"] == 2
    assert data["event_counts"]["add_to_cart"] == 1
    assert data["event_counts"]["submit_order"] == 1

    # Funnel rates (relative to storefront_view = 1)
    funnel = {s["event_name"]: s for s in data["funnel"]}
    assert funnel["storefront_view"]["rate"] == 1.0
    assert funnel["product_view"]["rate"] == 2.0
    assert funnel["add_to_cart"]["rate"] == 1.0
    assert funnel["submit_order"]["rate"] == 1.0
    assert funnel["begin_checkout"]["rate"] == 0.0

    # Daily series should have data
    assert data["daily_series"] is not None
    assert len(data["daily_series"]) == 1
    assert data["daily_series"][0]["storefront_views"] == 1
    assert data["daily_series"][0]["submissions"] == 1
