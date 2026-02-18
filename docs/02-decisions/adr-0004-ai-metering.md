# ADR-0004: AI Metering & Quota Enforcement

**Status**: Accepted
**Date**: 2026-02-17
**Deciders**: Rami (product owner), ChatGPT (brain/reviewer), Claude (implementor)

## Context
The platform provides an AI assistant on tenant storefronts. AI API calls have real cost (per-token pricing). We need to:
1. Prevent any single tenant from running up unbounded AI costs.
2. Track usage per tenant for billing transparency.
3. Enforce limits in real-time (not after the fact).

## Decision
**Redis-based quota tracking with soft/hard limits, backed by persistent usage logs in PostgreSQL.**

### Architecture

```
Storefront AI chat request
  → AI Gateway (app/services/ai_gateway.py)
    → Step 1: Reserve estimated tokens in Redis (INCRBY + compare against limits)
      → Over hard limit? → 429 "Quota exhausted"
      → Over soft limit? → Allow but flag for notification
    → Step 2: Call AI provider
      → On provider failure: rollback reservation (DECRBY estimated tokens)
    → Step 3: Adjust Redis counter (delta = actual - estimated; INCRBY delta)
    → Step 4: Log actual usage to ai_usage_log table (tenant_id, tokens, cost)
    → Return response
```

### Redis Keys

| Key | Type | TTL | Purpose |
|-----|------|-----|---------|
| `ai:quota:{tenant_id}:month:{YYYY-MM}` | Integer (token count) | 35 days | Running total of tokens used this month |
| `ai:limit:{tenant_id}:soft` | Integer | None (set on plan change) | Soft limit — trigger notification |
| `ai:limit:{tenant_id}:hard` | Integer | None (set on plan change) | Hard limit — block requests |

### Quota Lifecycle
1. **On tenant creation / plan change**: set `ai:limit:{tenant_id}:soft` and `:hard` in Redis from the plan's `ai_token_quota`.
2. **On AI request**: `INCRBY ai:quota:{tenant_id}:month:{YYYY-MM}` with estimated tokens (pre-call reservation). Compare against limits.
3. **On provider failure**: `DECRBY` the estimated tokens to release the reservation. No usage logged.
4. **On AI response (success)**: adjust Redis counter with delta (actual − estimated). Write `ai_usage_log` row with actual tokens.
5. **On month rollover**: old key expires naturally (35-day TTL). New month key starts at 0.

### Soft vs Hard Limits
- **Soft limit** (e.g., 80% of quota): request proceeds, but a Celery task fires a notification (email/Telegram) to the tenant owner. Notification sent once per billing period (dedup key in Redis).
- **Hard limit** (100% of quota): request blocked with `429` response. AI chat shows user-friendly "quota exhausted" message.

### Usage Logging (PostgreSQL)

Every successful AI call logs to `ai_usage_log`:

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `tenant_id` | UUID FK | RLS-enforced |
| `user_id` | UUID FK nullable | Null for anonymous storefront visitors |
| `conversation_id` | UUID FK | Links to `ai_conversations` |
| `model` | TEXT | Provider model identifier (e.g., `gpt-4o`, `claude-sonnet`) |
| `tokens_in` | INT | Input tokens |
| `tokens_out` | INT | Output tokens |
| `cost_usd` | NUMERIC(10,6) | Calculated from provider pricing |
| `created_at` | TIMESTAMPTZ | |

### AI Gateway — Single Entry Point

All AI calls go through `app/services/ai_gateway.py`. Route handlers never call provider SDKs directly. The gateway:
1. Validates tenant quota (reserve estimated tokens).
2. Sanitises input (strip PII markers if needed, enforce max input length).
3. Calls the AI provider with tenant-scoped system prompt.
4. On failure: rolls back reservation. On success: adjusts to actual, logs usage.
5. Returns structured response.

## Alternatives Considered

### Option A: Database-only tracking (no Redis)
| Pros | Cons |
|------|------|
| Simpler — one data store | `SELECT SUM(tokens) WHERE tenant_id = X AND month = Y` on every AI request adds latency |
| Transactionally consistent | Cannot enforce limits in real-time under concurrent requests (race conditions) |

### Option B: Redis-only (no PostgreSQL log)
| Pros | Cons |
|------|------|
| Fastest possible checks | Redis is volatile — data loss on restart means billing disputes |
| | No queryable history for dashboards, audits, or per-conversation breakdowns |

### Option C: Third-party metering (e.g., Stripe Metering, Lago)
| Pros | Cons |
|------|------|
| Built-in billing integration | Added vendor dependency, latency on metering API calls |
| | Overkill for MVP; we're not doing automated billing yet |

**Chosen: Option hybrid (Redis for real-time + PostgreSQL for persistence)**. Redis handles the hot path (quota check + reserve + adjust), PostgreSQL provides durable logs for dashboards and billing. If Redis loses data (unlikely with ElastiCache Multi-AZ), we rebuild counters from `ai_usage_log` via a Celery task.

## Consequences
- Every AI request adds ~1ms Redis overhead (INCRBY + GET). Acceptable.
- Redis counter can drift slightly from PostgreSQL totals under edge cases. Acceptable — the delta correction in Step 3 minimises drift, and hard limits have a small buffer (~2% over-quota tolerance before blocking).
- Failed provider calls do not consume quota (rollback ensures this).
- Plan changes must update Redis limits immediately (not just the DB).
- Monthly counter rebuild task should run on the 1st of each month as a safety net (reconcile Redis with `ai_usage_log`).
- Dashboard reads from `ai_usage_log` (PostgreSQL), not Redis — so dashboard data is always durable and accurate.

See `docs/01-architecture/ai-architecture.md` (to be created) for full gateway implementation details.
