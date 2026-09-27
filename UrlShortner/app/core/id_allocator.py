"""
Distributed, block-based unique ID allocator.

Problem: a naive "SELECT nextval / INSERT then use serial id" approach
hits the primary database on *every single* shorten request, which is
exactly the write contention we don't want on the one part of the
system that can't be trivially replicated (writes must go to a single
source of truth).

Solution: each application process pre-allocates a *block* of N
sequential IDs from Postgres in a single atomic round trip, then hands
out IDs from that block in memory until it's exhausted -- at which
point it fetches the next block. This turns "1 DB write per shorten
request" into "1 DB write per `id_block_size` shorten requests."

Trade-off, accepted deliberately: if a process crashes with unused IDs
still in its block, those IDs are simply never used again. At 62^6 ~=
56.8 billion addressable codes, this is an irrelevant amount of waste.
"""
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class BlockExhaustedError(Exception):
    """Raised internally when the in-memory block has no IDs left."""


class IdAllocator:
    """Per-process ID allocator backed by a shared Postgres counter.

    One instance of this should live for the lifetime of the app
    process (e.g., stored on `app.state`), not created per-request.
    """

    def __init__(self, block_size: int = 10_000):
        self._block_size = block_size
        self._next_id: int | None = None
        self._block_end: int | None = None  # exclusive upper bound of current block
        self._lock = asyncio.Lock()

    async def allocate_id(self, session: AsyncSession) -> int:
        """Return the next globally-unique integer ID.

        Only touches the database when the current in-memory block is
        exhausted; otherwise this is a pure in-memory operation and
        completes in microseconds.
        """
        async with self._lock:
            if self._next_id is None or self._next_id >= self._block_end:
                await self._fetch_new_block(session)

            allocated = self._next_id
            self._next_id += 1
            return allocated

    async def _fetch_new_block(self, session: AsyncSession) -> None:
        """Atomically reserve the next `block_size` IDs from Postgres.

        The UPDATE ... RETURNING is a single atomic statement -- two
        app instances racing this at the same time will always get
        disjoint ranges, enforced by Postgres row-level locking, with
        no explicit application-level locking required across processes.
        """
        result = await session.execute(
            text(
                """
                UPDATE id_counter
                SET current_value = current_value + :block_size
                RETURNING current_value - :block_size AS block_start
                """
            ),
            {"block_size": self._block_size},
        )
        row = result.one()
        await session.commit()

        self._next_id = row.block_start
        self._block_end = row.block_start + self._block_size
