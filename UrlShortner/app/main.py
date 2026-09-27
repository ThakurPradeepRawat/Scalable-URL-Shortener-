import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware import RateLimitMiddleware
from app.api.redirect import router as redirect_router
from app.api.shorten import router as shorten_router
from app.api.stats import router as stats_router
from app.cache.redis_client import get_redis
from app.core import click_flusher
from app.core.config import get_settings
from app.core.id_allocator import IdAllocator
from app.core.rate_limiter import TokenBucketRateLimiter

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # -- Startup --
    app.state.id_allocator = IdAllocator(block_size=settings.id_block_size)

    redis_client = get_redis()
    app.state.rate_limiter = TokenBucketRateLimiter(
        redis_client,
        capacity=settings.rate_limit_capacity,
        refill_rate_per_sec=settings.rate_limit_refill_per_sec,
    )

    flusher_task = asyncio.create_task(click_flusher.run_forever())

    yield

    # -- Shutdown --
    flusher_task.cancel()
    try:
        await flusher_task
    except asyncio.CancelledError:
        pass
    await redis_client.aclose()


app = FastAPI(
    title="PSBackend — Scalable URL Shortener",
    description="A distributed, horizontally-scalable URL shortening service.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)


@app.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok"}


# Route registration order matters here: Starlette matches routes in the
# order they're added and returns the first match. `/{short_code}` is a
# single-path-segment wildcard that would otherwise shadow fixed paths
# like `/health` or `/api/shorten` — so every specific route above is
# registered before the catch-all redirect router goes in last.
app.include_router(shorten_router)
app.include_router(stats_router)
app.include_router(redirect_router)
