"""
Thin cache-aside wrapper around Redis.

Eviction policy is set at the Redis server level (redis.conf /
docker-compose): `maxmemory-policy allkeys-lru`. URL access follows a
power-law distribution -- a small fraction of links account for most
clicks -- so LRU naturally keeps the "hot" working set resident without
needing to cache all 10M+ stored URLs.
"""
import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()

_redis_pool: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_pool


def _cache_key(short_code: str) -> str:
    return f"short:{short_code}"


async def get_cached_url(short_code: str) -> str | None:
    return await get_redis().get(_cache_key(short_code))


async def set_cached_url(short_code: str, long_url: str, ttl_seconds: int | None = None) -> None:
    """Write-through on creation: the very first redirect for a brand
    new (potentially viral) link is a cache hit, not a guaranteed miss.
    """
    ttl = ttl_seconds or settings.cache_ttl_seconds
    await get_redis().set(_cache_key(short_code), long_url, ex=ttl)


async def invalidate_cached_url(short_code: str) -> None:
    await get_redis().delete(_cache_key(short_code))


async def increment_click_counter(short_code: str) -> None:
    """Fire-and-forget increment on a Redis counter, batch-flushed to
    Postgres periodically (see app.core.click_flusher) instead of
    issuing an UPDATE on every single redirect.
    """
    await get_redis().incr(f"clicks:{short_code}")
