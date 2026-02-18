# AI Architecture

## Overview
The platform provides a conversational AI assistant on each tenant's storefront. All AI calls are routed through a single gateway service that enforces quotas, logs usage, and isolates tenant context.

---

## System Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Storefront UI  │────▶│  FastAPI Backend  │────▶│   AI Gateway    │
│  (chat widget)  │◀────│  POST /api/v1/    │◀────│  (ai_gateway.py)│
└─────────────────┘     │  ai/chat          │     └────────┬────────┘
                        └──────────────────┘              │
                                                          ▼
                                          ┌───────────────────────────┐
                                          │      Quota Check          │
                                          │  Redis INCRBY + compare   │
                                          │  Hard limit? → 429        │
                                          │  Soft limit? → allow+flag │
                                          └─────────────┬─────────────┘
                                                        │ pass
                                                        ▼
                                          ┌───────────────────────────┐
                                          │    Provider Call           │
                                          │  (Anthropic / OpenAI)     │
                                          │  Tenant-scoped sys prompt  │
                                          │  Max tokens capped         │
                                          └─────────────┬─────────────┘
                                                   success │ failure
                                              ┌────────────┴──────────┐
                                              ▼                       ▼
                                    ┌──────────────┐        ┌──────────────┐
                                    │ Delta adjust │        │  Rollback    │
                                    │ Redis counter│        │  DECRBY est. │
                                    │ Log to PG    │        │  No PG log   │
                                    └──────────────┘        └──────────────┘
```

---

## AI Gateway — `app/services/ai_gateway.py`

Single entry point for all AI calls. Route handlers never import provider SDKs directly.

### Responsibilities
1. **Quota enforcement** — reserve estimated tokens in Redis before calling provider (see ADR-0004).
2. **Input sanitisation** — enforce max input length, strip known PII patterns if configured.
3. **Tenant context injection** — build system prompt with tenant-specific instructions (storefront name, product catalog summary, tone).
4. **Provider call** — call AI provider with timeout and retry (1 retry, exponential backoff, 30s max).
5. **Failure rollback** — on provider error or timeout, DECRBY estimated tokens from Redis. No usage logged.
6. **Usage adjustment** — on success, adjust Redis counter (delta = actual − estimated). Write `ai_usage_log` row.
7. **Response formatting** — return structured response to the route handler.

### Pseudocode

```python
# app/services/ai_gateway.py

class AIGateway:
    def __init__(self, redis: Redis, db: AsyncSession, provider: AIProvider):
        self.redis = redis
        self.db = db
        self.provider = provider

    async def chat(
        self,
        tenant_id: UUID,
        conversation_id: UUID,
        user_message: str,
        user_id: UUID | None = None,  # None for anonymous storefront visitors
    ) -> AIResponse:

        # 1. Estimate tokens (rough: input chars / 4 + max_output_tokens)
        estimated = self._estimate_tokens(user_message)

        # 2. Reserve in Redis
        quota_key = f"ai:quota:{tenant_id}:month:{now_month()}"
        new_total = await self.redis.incrby(quota_key, estimated)
        if not await self.redis.exists(quota_key + ":ttl_set"):
            await self.redis.expire(quota_key, 35 * 86400)
            await self.redis.set(quota_key + ":ttl_set", 1, ex=35 * 86400)

        hard_limit = int(await self.redis.get(f"ai:limit:{tenant_id}:hard") or 0)
        soft_limit = int(await self.redis.get(f"ai:limit:{tenant_id}:soft") or 0)

        if hard_limit and new_total > hard_limit:
            await self.redis.decrby(quota_key, estimated)  # release
            raise QuotaExhaustedError(tenant_id)

        if soft_limit and new_total > soft_limit:
            await self._notify_soft_limit(tenant_id)  # async Celery task, deduped

        # 3. Build messages with tenant system prompt
        system_prompt = await self._build_system_prompt(tenant_id)
        messages = await self._load_conversation(conversation_id, user_message)

        # 4. Call provider
        try:
            result = await self.provider.chat(
                system=system_prompt,
                messages=messages,
                max_tokens=1024,
                timeout=30,
            )
        except AIProviderError:
            await self.redis.decrby(quota_key, estimated)  # rollback
            raise

        # 5. Adjust Redis with actual usage
        actual = result.tokens_in + result.tokens_out
        delta = actual - estimated
        if delta != 0:
            await self.redis.incrby(quota_key, delta)

        # 6. Log to PostgreSQL
        usage_log = AIUsageLog(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            model=result.model,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=self._calculate_cost(result),
        )
        self.db.add(usage_log)

        # 7. Append to conversation
        await self._append_to_conversation(conversation_id, user_message, result.text)

        return AIResponse(text=result.text, tokens_used=actual)
```

---

## Tenant System Prompt

Each tenant gets a dynamically-built system prompt injected before the user's message:

```
You are a helpful assistant for {tenant.name}.
You help customers with questions about products and services.

Available products/services:
{catalog_summary}

Rules:
- Be friendly, concise, and helpful.
- If a customer wants to place an order or make a donation, collect their name,
  phone, and the items/amount, then confirm.
- Never discuss other tenants or the platform itself.
- If you don't know the answer, say so and suggest the customer contact the team.
```

The catalog summary is cached in Redis (`ai:catalog:{tenant_id}`, 5-minute TTL) to avoid DB hits on every AI call.

---

## Conversation Storage

`ai_conversations.messages` stores the full message history as JSONB:

```json
[
  {"role": "system", "content": "..."},
  {"role": "user", "content": "What products do you have?", "ts": "2026-02-17T10:00:00Z"},
  {"role": "assistant", "content": "We have...", "ts": "2026-02-17T10:00:01Z"}
]
```

**Context window management**: if the conversation exceeds the provider's context window, the gateway truncates older messages (keeping the system prompt and last N turns). MVP: keep last 10 turns.

---

## Provider Abstraction

```python
# app/services/ai_provider.py

class AIProvider(Protocol):
    async def chat(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int,
        timeout: int,
    ) -> ProviderResult: ...

class AnthropicProvider(AIProvider):
    """Wraps the Anthropic SDK."""
    ...

class OpenAIProvider(AIProvider):
    """Wraps the OpenAI SDK."""
    ...
```

MVP ships with one provider (configurable via `/{env}/ai/provider` in SSM). The abstraction allows switching providers without changing gateway logic.

---

## Cost Calculation

```python
# Pricing table (loaded from config, not hardcoded)
PRICING = {
    "claude-sonnet": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "gpt-4o": {"input_per_1k": 0.005, "output_per_1k": 0.015},
}

def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> Decimal:
    p = PRICING[model]
    return Decimal(str(
        (tokens_in / 1000) * p["input_per_1k"] +
        (tokens_out / 1000) * p["output_per_1k"]
    )).quantize(Decimal("0.000001"))  # NUMERIC(10,6)
```

Pricing config stored in SSM (`/{env}/ai/pricing`), updated when provider pricing changes. Not hardcoded.

---

## Security Controls

| Control | Implementation |
|---------|---------------|
| Quota enforcement | Redis reserve/rollback pattern (ADR-0004) |
| Input length | Max 2,000 chars per user message (configurable) |
| Output length | `max_tokens=1024` per response (configurable per plan) |
| Rate limiting | Per-session: 10 messages / 5 min. Per-IP: see security.md §6 |
| PII in prompts | System prompt instructs AI not to request sensitive data (card numbers, civil IDs). App-level regex strips known PII patterns before sending. |
| Tenant isolation | System prompt is tenant-specific. Conversations are RLS-scoped. No cross-tenant context. |
| API key security | Provider API key in Secrets Manager (`/{env}/ai/api-key`). Loaded once at startup, refreshed on rotation. |
| Logging | Token usage logged per call. Conversation content logged in DB (RLS-scoped), never in application logs. |

---

## Checklist

- [ ] `ai_gateway.py` is the only module that imports provider SDKs.
- [ ] Quota reserve/rollback implemented per ADR-0004 flow.
- [ ] Soft limit notification fires via Celery, deduped per tenant per month.
- [ ] System prompt includes tenant name + catalog summary (cached in Redis).
- [ ] Conversation truncation to last 10 turns when context window exceeded.
- [ ] Provider abstraction layer supports swapping providers via config.
- [ ] Pricing config in SSM, not hardcoded.
- [ ] Max input length enforced (2,000 chars default).
- [ ] `max_tokens` capped per response.
- [ ] Per-session + per-IP rate limits on AI chat endpoint.
- [ ] Provider API key loaded from Secrets Manager.
- [ ] AI usage dashboard reads from `ai_usage_log` (PostgreSQL), not Redis.
- [ ] Integration test: quota exceeded → 429, no usage logged, Redis counter unchanged.
- [ ] Integration test: provider failure → rollback, no usage logged.
