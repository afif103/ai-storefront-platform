"""Health check endpoint."""

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

router = APIRouter()


@router.get("/health")
async def health_check():
    """Check DB and Redis connectivity."""
    db_status = "ok"
    redis_status = "ok"

    # Check database
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # Check Redis
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
    except Exception:
        redis_status = "error"

    status = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return {
        "status": status,
        "db": db_status,
        "redis": redis_status,
        "version": "0.1.0",
    }
