import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()

# Single shared connection pool; decode_responses gives us str in/out.
redis_client: redis.Redis = redis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
    socket_connect_timeout=settings.request_timeout_seconds,
    socket_timeout=settings.request_timeout_seconds,
    health_check_interval=30,
)


async def get_redis() -> redis.Redis:
    return redis_client


async def close_redis() -> None:
    await redis_client.aclose()
