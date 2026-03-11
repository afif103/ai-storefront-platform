"""AI gateway — single orchestrator for all AI chat requests.

Flow: validate → rate-limit → reserve quota → build prompt → call provider
     → adjust quota → log usage → save conversation → return response.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai_conversation import AIConversation
from app.models.ai_usage_log import AIUsageLog
from app.models.product import Product
from app.models.tenant import Tenant
from app.services.ai_provider import AIProvider, AIResponse
from app.services.ai_quota import (
    adjust_tokens,
    check_rate_limit,
    reserve_tokens,
    rollback_tokens,
)

# Pricing per 1k tokens (fallback; production reads from SSM)
_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input_per_1k": 0.005, "output_per_1k": 0.015},
    "gpt-4o-mini": {"input_per_1k": 0.00015, "output_per_1k": 0.0006},
    "llama-3.3-70b-versatile": {"input_per_1k": 0.00059, "output_per_1k": 0.00079},
    "claude-sonnet-4-5-20250514": {"input_per_1k": 0.003, "output_per_1k": 0.015},
}

_MAX_CONTEXT_TURNS = 10  # keep last N user+assistant turn pairs
_ESTIMATED_TOKENS = 500  # conservative estimate for quota reservation


@dataclass(frozen=True)
class ChatResult:
    conversation_id: uuid.UUID
    reply: str
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal


class AIGatewayError(Exception):
    """Raised for quota/rate-limit/validation failures."""

    def __init__(self, detail: str, error_type: str, status_code: int = 429) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error_type = error_type
        self.status_code = status_code


def _compute_cost(model: str, tokens_in: int, tokens_out: int) -> Decimal:
    pricing = _PRICING.get(model, {"input_per_1k": 0.003, "output_per_1k": 0.015})
    cost = (tokens_in / 1000) * pricing["input_per_1k"] + (tokens_out / 1000) * pricing[
        "output_per_1k"
    ]
    return Decimal(str(round(cost, 6)))


async def _build_system_prompt(db: AsyncSession, tenant: Tenant) -> str:
    """Build system prompt with tenant name + catalog summary."""
    result = await db.execute(
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.sort_order, Product.id)
        .limit(50)
    )
    products = list(result.scalars().all())

    catalog_lines: list[str] = []
    for p in products:
        if p.price_amount:
            currency = p.currency or tenant.default_currency
            price = f"{p.price_amount} {currency}"
        else:
            price = "Price not set"
        catalog_lines.append(f"- {p.name}: {price}")

    catalog_summary = "\n".join(catalog_lines) if catalog_lines else "No products listed yet."

    return (
        f"You are a helpful assistant for {tenant.name}.\n"
        f"You help team members with questions about orders, donations, pledges, "
        f"products, and general business operations.\n\n"
        f"Available products/services:\n{catalog_summary}\n\n"
        f"Rules:\n"
        f"- Be friendly, concise, and helpful.\n"
        f"- Answer questions about order statuses, donation tracking, and business metrics.\n"
        f"- If you don't know the answer, say so.\n"
        f"- Never discuss other tenants or the platform itself."
    )


async def _get_or_create_conversation(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> AIConversation:
    """Load existing conversation or create a new one."""
    result = await db.execute(
        select(AIConversation).where(
            AIConversation.tenant_id == tenant_id,
            AIConversation.user_id == user_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is not None:
        return conversation

    conversation = AIConversation(
        tenant_id=tenant_id,
        user_id=user_id,
        messages=[],
    )
    db.add(conversation)
    await db.flush()
    return conversation


def _trim_context(messages: list[dict], max_turns: int) -> list[dict]:
    """Keep last max_turns user+assistant pairs."""
    if len(messages) <= max_turns * 2:
        return messages
    return messages[-(max_turns * 2) :]


async def handle_chat(
    db: AsyncSession,
    tenant: Tenant,
    user_id: uuid.UUID,
    message: str,
    provider: AIProvider,
) -> ChatResult:
    """Full AI chat pipeline."""
    tenant_id = tenant.id

    # 1. Validate input length
    if len(message) > settings.AI_MAX_INPUT_CHARS:
        raise AIGatewayError(
            f"Message exceeds {settings.AI_MAX_INPUT_CHARS} character limit",
            "validation_error",
            status_code=422,
        )

    # 2. Rate limit per user
    if not await check_rate_limit(str(tenant_id), str(user_id)):
        raise AIGatewayError(
            "Rate limit exceeded. Please wait a moment.",
            "rate_limited",
        )

    # 3. Reserve quota
    hard_limit = tenant.plan.ai_token_quota if tenant.plan else 0
    quota = await reserve_tokens(str(tenant_id), _ESTIMATED_TOKENS, hard_limit)
    if not quota.allowed:
        raise AIGatewayError(
            "AI token quota exhausted for this month.",
            "quota_exhausted",
        )

    # 4. Load/create conversation
    conversation = await _get_or_create_conversation(db, tenant_id, user_id)

    # 5. Build messages for provider
    system_prompt = await _build_system_prompt(db, tenant)
    context = _trim_context(list(conversation.messages), _MAX_CONTEXT_TURNS)
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
        # Rollback quota reservation on failure
        await rollback_tokens(str(tenant_id), _ESTIMATED_TOKENS)
        raise

    # 7. Adjust quota with actual usage
    actual_tokens = ai_response.tokens_in + ai_response.tokens_out
    delta = actual_tokens - _ESTIMATED_TOKENS
    await adjust_tokens(str(tenant_id), delta)

    # 8. Save conversation (append user + assistant messages)
    updated_messages = list(conversation.messages)
    updated_messages.append({"role": "user", "content": message})
    updated_messages.append({"role": "assistant", "content": ai_response.content})
    conversation.messages = updated_messages
    conversation.updated_at = datetime.now(UTC)
    await db.flush()

    # 9. Log usage
    cost = _compute_cost(ai_response.model, ai_response.tokens_in, ai_response.tokens_out)
    usage_log = AIUsageLog(
        tenant_id=tenant_id,
        user_id=user_id,
        conversation_id=conversation.id,
        model=ai_response.model,
        tokens_in=ai_response.tokens_in,
        tokens_out=ai_response.tokens_out,
        cost_usd=cost,
    )
    db.add(usage_log)
    await db.flush()

    return ChatResult(
        conversation_id=conversation.id,
        reply=ai_response.content,
        tokens_in=ai_response.tokens_in,
        tokens_out=ai_response.tokens_out,
        cost_usd=cost,
    )
