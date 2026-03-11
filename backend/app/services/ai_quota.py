"""Redis-backed AI token quota: reserve / adjust / rollback.

Keys:
  ai:quota:{tenant_id}:month:{YYYY-MM}  — running token total (TTL 35 days)
  ai:rate:{tenant_id}:{user_id}          — message count (TTL 5 min)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import redis.asyncio as aioredis

from app.core.config import settings

_RATE_LIMIT_MESSAGES = 30  # per user per 5-min window
_RATE_LIMIT_WINDOW = 300  # seconds


@dataclass(frozen=True)
class QuotaResult:
    allowed: bool
    over_soft: bool
    reason: str | None = None


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL)


def _month_key(tenant_id: str) -> str:
    month = datetime.now(UTC).strftime("%Y-%m")
    return f"ai:quota:{tenant_id}:month:{month}"


def _rate_key(tenant_id: str, user_id: str) -> str:
    return f"ai:rate:{tenant_id}:{user_id}"


async def check_rate_limit(tenant_id: str, user_id: str) -> bool:
    """Return True if the user is within the per-user rate limit."""
    r = await _get_redis()
    try:
        key = _rate_key(tenant_id, user_id)
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, _RATE_LIMIT_WINDOW)
        return count <= _RATE_LIMIT_MESSAGES
    finally:
        await r.aclose()


_SF_RATE_LIMIT_MESSAGES = 10  # per session per 5-min window


async def check_session_rate_limit(tenant_id: str, session_id: str) -> bool:
    """Return True if a storefront visitor session is within rate limit."""
    r = await _get_redis()
    try:
        key = f"ai:sf_rate:{tenant_id}:{session_id}"
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, _RATE_LIMIT_WINDOW)
        return count <= _SF_RATE_LIMIT_MESSAGES
    finally:
        await r.aclose()


_ANALYTICS_RATE_LIMIT_MESSAGES = 60  # per session+ip per 5-min window


async def check_analytics_rate_limit(tenant_id: str, session_id: str, ip_hash: str) -> bool:
    """Return True if an analytics ingest session is within rate limit."""
    r = await _get_redis()
    try:
        key = f"analytics:rate:{tenant_id}:{session_id}:{ip_hash}"
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, _RATE_LIMIT_WINDOW)
        return count <= _ANALYTICS_RATE_LIMIT_MESSAGES
    finally:
        await r.aclose()


async def reserve_tokens(tenant_id: str, estimated: int, hard_limit: int) -> QuotaResult:
    """Reserve estimated tokens. Returns whether the request is allowed."""
    if hard_limit <= 0:
        # No quota configured — allow unlimited
        return QuotaResult(allowed=True, over_soft=False)

    r = await _get_redis()
    try:
        key = _month_key(tenant_id)
        new_total = await r.incrby(key, estimated)
        # Set TTL on first use (35 days)
        ttl = await r.ttl(key)
        if ttl == -1:
            await r.expire(key, 35 * 86400)

        soft_limit = int(hard_limit * 0.8)

        if new_total > hard_limit:
            # Over hard limit — rollback and deny
            await r.decrby(key, estimated)
            return QuotaResult(allowed=False, over_soft=True, reason="quota_exhausted")

        return QuotaResult(
            allowed=True,
            over_soft=new_total > soft_limit,
        )
    finally:
        await r.aclose()


async def adjust_tokens(tenant_id: str, delta: int) -> None:
    """Adjust after actual usage known: delta = actual - estimated."""
    if delta == 0:
        return
    r = await _get_redis()
    try:
        await r.incrby(_month_key(tenant_id), delta)
    finally:
        await r.aclose()


async def rollback_tokens(tenant_id: str, estimated: int) -> None:
    """Release reserved tokens on provider failure."""
    r = await _get_redis()
    try:
        await r.decrby(_month_key(tenant_id), estimated)
    finally:
        await r.aclose()
