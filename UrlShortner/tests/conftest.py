import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.cache.redis_client as redis_module
from app.core.id_allocator import IdAllocator
from app.db.models import Base
from app.db.session import get_primary_session, get_replica_session
from app.main import app


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("INSERT INTO id_counter (id, current_value) VALUES (1, 0)"))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_engine, monkeypatch):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_primary_session] = _get_session
    app.dependency_overrides[get_replica_session] = _get_session

    # Swap the real Redis client for an in-memory fake so tests don't
    # need a running Redis instance, without changing any app code.
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_module, "_redis_pool", fake_redis)

    # Set up just the app.state the routes need directly, rather than
    # running the full lifespan (which would spin up the background
    # click-flusher loop and a real rate limiter against Redis Lua
    # scripting support that varies by fakeredis version).
    app.state.id_allocator = IdAllocator(block_size=100)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
