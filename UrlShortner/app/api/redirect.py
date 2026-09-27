from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_client import get_cached_url, increment_click_counter, set_cached_url
from app.db.models import ShortURL
from app.db.session import get_replica_session

router = APIRouter(tags=["redirect"])


@router.get("/{short_code}")
async def redirect_to_long_url(
    short_code: str,
    session: AsyncSession = Depends(get_replica_session),
) -> RedirectResponse:
    # 1. Cache-aside read. ~95% of production traffic is satisfied here,
    #    at ~1-2ms, without ever touching Postgres.
    cached_url = await get_cached_url(short_code)
    if cached_url is not None:
        await increment_click_counter(short_code)
        return _redirect(cached_url)

    # 2. Cache miss -> read from a replica, never the primary. Isolates
    #    the dominant read path from write contention on the source of truth.
    result = await session.execute(select(ShortURL).where(ShortURL.short_code == short_code))
    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found")

    if record.expires_at is not None and record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL has expired")

    # 3. Populate the cache so the next request for this code is a hit.
    ttl_seconds = None
    if record.expires_at is not None:
        ttl_seconds = max(1, int((record.expires_at - datetime.now(timezone.utc)).total_seconds()))
    await set_cached_url(short_code, record.long_url, ttl_seconds=ttl_seconds)

    await increment_click_counter(short_code)
    return _redirect(record.long_url)


def _redirect(long_url: str) -> RedirectResponse:
    # 302, deliberately not 301: a 301 gets cached by the client browser,
    # which would (a) stop us from ever seeing repeat clicks for
    # analytics, and (b) make the mapping effectively immutable from the
    # client's point of view even after we update or expire it server-side.
    return RedirectResponse(url=long_url, status_code=status.HTTP_302_FOUND)
