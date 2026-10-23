"""Shared Redis client (used for pub/sub events and health checks)."""

from redis.asyncio import Redis

from app.core.config import get_settings

redis = Redis.from_url(get_settings().redis_url, decode_responses=True)


async def check_redis() -> bool:
    try:
        return bool(await redis.ping())
    except Exception:
        return False
