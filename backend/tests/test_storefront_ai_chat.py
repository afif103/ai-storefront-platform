"""Storefront AI chat integration tests with mocked provider."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storefront_ai_conversation import StorefrontAIConversation
from app.models.storefront_ai_usage_log import StorefrontAIUsageLog
from app.services.ai_provider import AIResponse
from tests.conftest import auth_headers

pytestmark = pytest.mark.m4


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _mock_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.chat = AsyncMock(
        return_value=AIResponse(
            content="We have great products!",
            tokens_in=40,
            tokens_out=20,
            model="gpt-4o",
        )
    )
    return provider


async def _create_tenant(client: AsyncClient) -> tuple[str, str]:
    """Create tenant, return (slug, tenant_id)."""
    uid = _uid()
    headers = auth_headers(sub=f"sf-ai-{uid}", email=f"sf-ai-{uid}@test.com")
    headers["Content-Type"] = "application/json"

    r = await client.post(
        "/api/v1/tenants/",
        json={"name": f"SF AI {uid}", "slug": f"sf-ai-{uid}"},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["slug"], r.json()["id"]


async def test_storefront_chat_success(client: AsyncClient, db: AsyncSession):
    """POST /storefront/{slug}/ai/chat returns reply and persists conversation."""
    slug, tenant_id = await _create_tenant(client)
    session_id = f"sess-{_uid()}"

    with patch(
        "app.services.ai_provider.get_provider",
        return_value=_mock_provider(),
    ):
        r = await client.post(
            f"/api/v1/storefront/{slug}/ai/chat",
            json={"session_id": session_id, "message": "What do you sell?"},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["reply"] == "We have great products!"
    assert data["conversation_id"] is not None
    assert data["usage"]["tokens_in"] == 40
    assert data["usage"]["tokens_out"] == 20

    # Verify conversation persisted
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    result = await db.execute(
        select(StorefrontAIConversation).where(StorefrontAIConversation.session_id == session_id)
    )
    conv = result.scalar_one()
    assert len(conv.messages) == 2
    assert conv.messages[0]["role"] == "user"
    assert conv.messages[1]["role"] == "assistant"

    # Verify usage log
    log_result = await db.execute(
        select(StorefrontAIUsageLog).where(StorefrontAIUsageLog.conversation_id == conv.id)
    )
    log = log_result.scalar_one()
    assert log.tokens_in == 40
    assert log.tokens_out == 20


async def test_storefront_chat_continues_conversation(client: AsyncClient):
    """Second message reuses the same conversation."""
    slug, _tid = await _create_tenant(client)
    session_id = f"sess-{_uid()}"

    with patch(
        "app.services.ai_provider.get_provider",
        return_value=_mock_provider(),
    ):
        r1 = await client.post(
            f"/api/v1/storefront/{slug}/ai/chat",
            json={"session_id": session_id, "message": "Hello"},
        )
        assert r1.status_code == 200
        conv_id_1 = r1.json()["conversation_id"]

        r2 = await client.post(
            f"/api/v1/storefront/{slug}/ai/chat",
            json={"session_id": session_id, "message": "Tell me more"},
        )
        assert r2.status_code == 200
        conv_id_2 = r2.json()["conversation_id"]

    assert conv_id_1 == conv_id_2


async def test_storefront_chat_empty_message_rejected(client: AsyncClient):
    """Empty message returns 422."""
    slug, _tid = await _create_tenant(client)

    r = await client.post(
        f"/api/v1/storefront/{slug}/ai/chat",
        json={"session_id": "sess-x", "message": ""},
    )
    assert r.status_code == 422


async def test_storefront_chat_tenant_isolation(client: AsyncClient):
    """Two tenants get separate conversations for same session_id."""
    slug_a, _tid_a = await _create_tenant(client)
    slug_b, _tid_b = await _create_tenant(client)
    session_id = f"shared-sess-{_uid()}"

    with patch(
        "app.services.ai_provider.get_provider",
        return_value=_mock_provider(),
    ):
        r_a = await client.post(
            f"/api/v1/storefront/{slug_a}/ai/chat",
            json={"session_id": session_id, "message": "Hi A"},
        )
        assert r_a.status_code == 200

        r_b = await client.post(
            f"/api/v1/storefront/{slug_b}/ai/chat",
            json={"session_id": session_id, "message": "Hi B"},
        )
        assert r_b.status_code == 200

    # Different conversations (different tenants)
    assert r_a.json()["conversation_id"] != r_b.json()["conversation_id"]


async def test_storefront_chat_bad_slug_404(client: AsyncClient):
    """Unknown slug returns 404."""
    r = await client.post(
        "/api/v1/storefront/no-such-store/ai/chat",
        json={"session_id": "x", "message": "hi"},
    )
    assert r.status_code == 404
