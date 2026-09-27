"""
Token bucket rate limiter, implemented atomically in Redis via a Lua
script.

Why token bucket over a fixed-window counter: a fixed window
("max 100 requests per minute") allows a full 2x burst at the window
boundary -- 100 requests at 11:59:59 and another 100 at 12:00:00, i.e.
200 requests in a two-second span. A token bucket enforces a true
steady-state rate while still tolerating short, legitimate bursts
(e.g., a client batch-shortening several URLs at once).

Why a Lua script rather than separate GET/SET calls from Python: the
read-modify-write of "check tokens, decrement, write back" must be
atomic, or two concurrent requests from the same client could both
read the same token count and both be allowed through. Redis executes
Lua scripts atomically, so this is race-free without any external
locking.
"""
from dataclasses import dataclass

import redis.asyncio as redis

_TOKEN_BUCKET_SCRIPT = """
-- KEYS[1] = bucket key
-- ARGV[1] = capacity (max tokens)
-- ARGV[2] = refill_rate (tokens per second)
-- ARGV[3] = now (unix timestamp, float seconds)
-- ARGV[4] = requested tokens (usually 1)

local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local bucket = redis.call("HMGET", KEYS[1], "tokens", "last_refill")
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

-- Refill based on elapsed time since the bucket was last touched.
local elapsed = math.max(0, now - last_refill)
tokens = math.min(capacity, tokens + elapsed * refill_rate)

local allowed = 0
if tokens >= requested then
    tokens = tokens - requested
    allowed = 1
end

redis.call("HMSET", KEYS[1], "tokens", tokens, "last_refill", now)
redis.call("EXPIRE", KEYS[1], 3600)

return { allowed, tokens }
"""


@dataclass
class RateLimitResult:
    allowed: bool
    remaining_tokens: float


class TokenBucketRateLimiter:
    def __init__(
        self,
        redis_client: redis.Redis,
        capacity: int = 20,
        refill_rate_per_sec: float = 10.0,
    ):
        self._redis = redis_client
        self._capacity = capacity
        self._refill_rate = refill_rate_per_sec
        self._script = redis_client.register_script(_TOKEN_BUCKET_SCRIPT)

    async def allow(self, client_id: str, cost: int = 1) -> RateLimitResult:
        import time

        key = f"ratelimit:{client_id}"
        allowed, remaining = await self._script(
            keys=[key],
            args=[self._capacity, self._refill_rate, time.time(), cost],
        )
        return RateLimitResult(allowed=bool(allowed), remaining_tokens=float(remaining))
