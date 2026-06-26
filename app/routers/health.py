import logging

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.redis_client import get_redis

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe: process is up. No external dependencies checked."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    db: AsyncSession = Depends(get_db),
    cache: redis.Redis = Depends(get_redis),
) -> dict:
    """Readiness probe: verify Postgres and Redis are reachable."""
    checks = {"postgres": "down", "redis": "down"}

    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = "up"
    except Exception:
        logger.exception("postgres readiness check failed")

    try:
        await cache.ping()
        checks["redis"] = "up"
    except Exception:
        logger.exception("redis readiness check failed")

    status = "ok" if all(v == "up" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
