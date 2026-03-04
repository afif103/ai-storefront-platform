"""Storefront AI chat gateway — buyer-facing, read-only assistant.

Separate from the dashboard gateway: uses session_id (not user_id),
separate tables, and a buyer-focused system prompt.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.product import Product
from app.models.storefront_ai_conversation import StorefrontAIConversation
from app.models.storefront_ai_usage_log import StorefrontAIUsageLog
from app.models.tenant import Tenant
from app.services.ai_gateway import _compute_cost
from app.services.ai_provider import AIProvider, AIResponse
from app.services.ai_quota import (
    adjust_tokens,
    check_session_rate_limit,
    reserve_tokens,
    rollback_tokens,
)

_MAX_CONTEXT_TURNS = 6  # fewer turns for buyer chat (cost control)
_ESTIMATED_TOKENS = 400


@dataclass(frozen=True)
class StorefrontChatResult:
    conversation_id: uuid.UUID
    reply: str
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal


class StorefrontAIGatewayError(Exception):
    def __init__(self, detail: str, error_type: str, status_code: int = 429) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error_type = error_type
        self.status_code = status_code


async def _build_buyer_prompt(db: AsyncSession, tenant: Tenant, slug: str) -> str:
    """System prompt framed for buyers browsing the storefront."""
    result = await db.execute(
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.sort_order, Product.id)
        .limit(50)
    )
    products = list(result.scalars().all())

    lines: list[str] = []
    for p in products:
        if p.price_amount:
            currency = p.currency or tenant.default_currency
            price = f"{p.price_amount} {currency}"
        else:
            price = "Price not set"
        desc = f" — {p.description}" if p.description else ""
        lines.append(f"- {p.name}: {price}{desc}")

    catalog = "\n".join(lines) if lines else "No products listed yet."

    return (
        f"You are a friendly shopping assistant for {tenant.name}.\n"
        f"Help visitors learn about products, answer questions, and guide "
        f"them toward placing an order, making a donation, or submitting a pledge.\n\n"
        f"Available products:\n{catalog}\n\n"
        f"Rules:\n"
        f"- Be concise, friendly, and helpful.\n"
        f"- You can describe products and answer questions about them.\n"
        f"- To place an order, direct the visitor to the checkout page.\n"
        f"- To donate, direct them to the donation page.\n"
        f"- To pledge, direct them to the pledge page.\n"
        f"- You CANNOT create orders, donations, or pledges yourself.\n"
        f"- Never discuss other stores, tenants, or the platform itself.\n"
        f"- If you don't know, say so."
    )


def _trim_context(messages: list[dict], max_turns: int) -> list[dict]:
    if len(messages) <= max_turns * 2:
        return messages
    return messages[-(max_turns * 2) :]


async def _get_or_create_conversation(
    db: AsyncSession, tenant_id: uuid.UUID, session_id: str
) -> StorefrontAIConversation:
    result = await db.execute(
        select(StorefrontAIConversation).where(
            StorefrontAIConversation.tenant_id == tenant_id,
            StorefrontAIConversation.session_id == session_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is not None:
        return conv

    conv = StorefrontAIConversation(
        tenant_id=tenant_id,
        session_id=session_id,
        messages=[],
    )
    db.add(conv)
    await db.flush()
    return conv


async def handle_storefront_chat(
    db: AsyncSession,
    tenant: Tenant,
    slug: str,
    session_id: str,
    message: str,
    provider: AIProvider,
    *,
    ai_token_quota: int = 0,
) -> StorefrontChatResult:
    """Full buyer chat pipeline."""
    tenant_id = tenant.id

    # 1. Validate input
    if len(message) > settings.AI_MAX_INPUT_CHARS:
        raise StorefrontAIGatewayError(
            f"Message exceeds {settings.AI_MAX_INPUT_CHARS} character limit",
            "validation_error",
            status_code=422,
        )

    # 2. Rate limit per session
    if not await check_session_rate_limit(str(tenant_id), session_id):
        raise StorefrontAIGatewayError(
            "Too many messages. Please wait a few minutes.",
            "rate_limited",
        )

    # 3. Reserve quota (shared tenant-level quota)
    hard_limit = ai_token_quota
    quota = await reserve_tokens(str(tenant_id), _ESTIMATED_TOKENS, hard_limit)
    if not quota.allowed:
        raise StorefrontAIGatewayError(
            "This store's AI assistant is temporarily unavailable.",
            "quota_exhausted",
        )

    # 4. Load/create conversation
    conv = await _get_or_create_conversation(db, tenant_id, session_id)

    # 5. Build messages
    system_prompt = await _build_buyer_prompt(db, tenant, slug)
    context = _trim_context(list(conv.messages), _MAX_CONTEXT_TURNS)
    provider_messages = [
        {"role": "system", "content": system_prompt},
        *context,
        {"role": "user", "content": message},
    ]

    # 6. Call provider
    ai_response: AIResponse
    try:
        ai_response = await provider.chat(
            provider_messages,
            max_tokens=settings.AI_MAX_OUTPUT_TOKENS,
        )
    except Exception:
        await rollback_tokens(str(tenant_id), _ESTIMATED_TOKENS)
        raise

    # 7. Adjust quota
    actual = ai_response.tokens_in + ai_response.tokens_out
    await adjust_tokens(str(tenant_id), actual - _ESTIMATED_TOKENS)

    # 8. Save conversation
    updated = list(conv.messages)
    updated.append({"role": "user", "content": message})
    updated.append({"role": "assistant", "content": ai_response.content})
    conv.messages = updated
    conv.updated_at = datetime.now(UTC)
    await db.flush()

    # 9. Log usage
    cost = _compute_cost(ai_response.model, ai_response.tokens_in, ai_response.tokens_out)
    log = StorefrontAIUsageLog(
        tenant_id=tenant_id,
        session_id=session_id,
        conversation_id=conv.id,
        model=ai_response.model,
        tokens_in=ai_response.tokens_in,
        tokens_out=ai_response.tokens_out,
        cost_usd=cost,
    )
    db.add(log)
    await db.flush()

    return StorefrontChatResult(
        conversation_id=conv.id,
        reply=ai_response.content,
        tokens_in=ai_response.tokens_in,
        tokens_out=ai_response.tokens_out,
        cost_usd=cost,
    )
