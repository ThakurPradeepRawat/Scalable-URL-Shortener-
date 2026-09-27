import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.id_allocator import IdAllocator
from app.db.models import Base


@pytest_asyncio.fixture
async def session_factory():
    # In-memory SQLite stands in for Postgres here purely to exercise the
    # allocator's block logic; it relies only on `UPDATE ... RETURNING`,
    # which SQLite 3.35+ also supports.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("INSERT INTO id_counter (id, current_value) VALUES (1, 0)"))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_ids_are_sequential_within_a_block(session_factory):
    allocator = IdAllocator(block_size=5)

    async with session_factory() as session:
        ids = [await allocator.allocate_id(session) for _ in range(5)]

    assert ids == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_allocator_fetches_a_new_block_when_exhausted(session_factory):
    allocator = IdAllocator(block_size=3)

    async with session_factory() as session:
        first_block = [await allocator.allocate_id(session) for _ in range(3)]
        second_block = [await allocator.allocate_id(session) for _ in range(3)]

    assert first_block == [0, 1, 2]
    assert second_block == [3, 4, 5]  # contiguous with the first block, no gaps or overlaps


@pytest.mark.asyncio
async def test_two_allocators_never_overlap(session_factory):
    # Simulates two app processes racing to allocate blocks against the
    # same counter row -- they must receive disjoint ranges.
    allocator_a = IdAllocator(block_size=10)
    allocator_b = IdAllocator(block_size=10)

    async with session_factory() as session:
        ids_a = [await allocator_a.allocate_id(session) for _ in range(10)]
        ids_b = [await allocator_b.allocate_id(session) for _ in range(10)]

    assert set(ids_a).isdisjoint(set(ids_b))
