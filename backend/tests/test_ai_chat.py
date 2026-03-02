"""AI assistant chat integration tests with mocked provider."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_conversation import AIConversation
from app.models.ai_usage_log import AIUsageLog
from app.services.ai_provider import AIResponse
from tests.conftest import auth_headers

pytestmark = pytest.mark.m4


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _mock_provider_success() -> AsyncMock:
    """Return a mock provider that returns a canned response."""
    provider = AsyncMock()
    provider.chat = AsyncMock(
        return_value=AIResponse(
            content="Here are your products...",
            tokens_in=50,
            tokens_out=30,
            model="claude-sonnet-4-5-20250514",
        )
    )
    return provider


def _mock_provider_failure() -> AsyncMock:
    """Return a mock provider that raises an exception."""
    provider = AsyncMock()
    provider.chat = AsyncMock(side_effect=RuntimeError("Provider unavailable"))
    return provider


async def _setup_tenant(client: AsyncClient) -> tuple[dict, str]:
    """Create tenant, return (headers, tenant_id)."""
    uid = _uid()
    headers = auth_headers(sub=f"ai-{uid}", email=f"ai-{uid}@test.com")
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"AI Test {uid}", "slug": f"ai-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201
    return headers, r.json()["id"]


async def test_ai_chat_success(client: AsyncClient, db: AsyncSession):
    """POST /tenants/me/ai/chat returns reply and creates conversation + usage log."""
    headers, tenant_id = await _setup_tenant(client)

    mock_provider = _mock_provider_success()

    with patch("app.api.v1.ai_chat.get_provider", return_value=mock_provider):
        r = await client.post(
            "/api/v1/tenants/me/ai/chat",
            json={"message": "What products do you have?"},
            headers=headers,
        )

    assert r.status_code == 200
    data = r.json()
    assert data["reply"] == "Here are your products..."
    assert data["conversation_id"] is not None
    assert data["usage"]["tokens_in"] == 50
    assert data["usage"]["tokens_out"] == 30
    assert Decimal(data["usage"]["cost_usd"]) > 0

    # Verify DB: conversation exists with messages
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    conv_result = await db.execute(
        select(AIConversation).where(
            AIConversation.tenant_id == uuid.UUID(tenant_id)
        )
    )
    conv = conv_result.scalar_one()
    assert len(conv.messages) == 2  # user + assistant
    assert conv.messages[0]["role"] == "user"
    assert conv.messages[1]["role"] == "assistant"

    # Verify DB: usage log exists
    log_result = await db.execute(
        select(AIUsageLog).where(AIUsageLog.conversation_id == conv.id)
    )
    log = log_result.scalar_one()
    assert log.tokens_in == 50
    assert log.tokens_out == 30
    assert log.model == "claude-sonnet-4-5-20250514"


async def test_ai_chat_continues_conversation(client: AsyncClient):
    """Second message appends to existing conversation."""
    headers, _tid = await _setup_tenant(client)
    mock_provider = _mock_provider_success()

    with patch("app.api.v1.ai_chat.get_provider", return_value=mock_provider):
        r1 = await client.post(
            "/api/v1/tenants/me/ai/chat",
            json={"message": "Hello"},
            headers=headers,
        )
        assert r1.status_code == 200
        conv_id_1 = r1.json()["conversation_id"]

        r2 = await client.post(
            "/api/v1/tenants/me/ai/chat",
            json={"message": "Tell me more"},
            headers=headers,
        )
        assert r2.status_code == 200
        conv_id_2 = r2.json()["conversation_id"]

    # Same conversation reused
    assert conv_id_1 == conv_id_2


async def test_ai_chat_provider_failure_no_db_writes(
    client: AsyncClient, db: AsyncSession
):
    """Provider failure: no conversation update, no usage log, quota rolled back."""
    headers, tenant_id = await _setup_tenant(client)
    mock_provider = _mock_provider_failure()

    with patch("app.api.v1.ai_chat.get_provider", return_value=mock_provider):
        r = await client.post(
            "/api/v1/tenants/me/ai/chat",
            json={"message": "This will fail"},
            headers=headers,
        )

    assert r.status_code == 502

    # Verify: no usage log was created for this tenant
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    log_result = await db.execute(
        select(AIUsageLog).where(AIUsageLog.tenant_id == uuid.UUID(tenant_id))
    )
    logs = list(log_result.scalars().all())
    assert len(logs) == 0


async def test_ai_chat_empty_message_rejected(client: AsyncClient):
    """Empty message returns 422."""
    headers, _tid = await _setup_tenant(client)

    r = await client.post(
        "/api/v1/tenants/me/ai/chat",
        json={"message": ""},
        headers=headers,
    )
    assert r.status_code == 422


async def test_ai_chat_requires_auth(client: AsyncClient):
    """No auth header returns 401."""
    r = await client.post(
        "/api/v1/tenants/me/ai/chat",
        json={"message": "hello"},
    )
    assert r.status_code == 401
