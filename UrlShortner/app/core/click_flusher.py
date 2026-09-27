"""
Periodically flushes buffered click counts from Redis into Postgres.

The redirect path never runs an UPDATE against `urls.click_count`
directly -- that would serialize writes on hot rows and put a write
on the critical path of the fastest, most frequent request in the
system. Instead, `increment_click_counter` does a Redis INCR (O(1),
no lock contention across popular codes), and this background task
periodically sweeps accumulated counters into Postgres in a single
batched statement.
"""
import asyncio
import logging

from sqlalchemy import text

from app.cache.redis_client import get_redis
from app.core.config import get_settings
from app.db.session import PrimarySession

logger = logging.getLogger("click_flusher")

_CLICK_KEY_PATTERN = "clicks:*"


async def flush_once() -> int:
    """Sweep all pending click counters into Postgres. Returns the
    number of short codes flushed. Exposed separately from the loop
    so it's directly unit-testable and callable on shutdown.
    """
    r = get_redis()
    flushed = 0

    async for key in r.scan_iter(match=_CLICK_KEY_PATTERN, count=500):
        short_code = key.split(":", 1)[1]
        # GETDEL atomically reads and clears the counter, so a click
        # arriving mid-flush is never lost -- it starts a fresh counter.
        count = await r.getdel(key)
        if not count:
            continue

        async with PrimarySession() as session:
            await session.execute(
                text(
                    "UPDATE urls SET click_count = click_count + :count "
                    "WHERE short_code = :short_code"
                ),
                {"count": int(count), "short_code": short_code},
            )
            await session.commit()
        flushed += 1

    return flushed


async def run_forever() -> None:
    settings = get_settings()
    while True:
        try:
            flushed = await flush_once()
            if flushed:
                logger.info("Flushed click counts for %d short codes", flushed)
        except Exception:
            logger.exception("Click flush cycle failed")
        await asyncio.sleep(settings.click_flush_interval_seconds)
