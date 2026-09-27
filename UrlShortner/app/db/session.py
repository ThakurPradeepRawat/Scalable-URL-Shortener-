"""
Primary/replica session routing.

Writes (POST /shorten, ID block allocation, batched click flushes) go
through `get_primary_session`. Cache-miss reads (GET /{short_code}
falling through Redis) go through `get_replica_session`. This is what
keeps the redirect path -- the overwhelming majority of traffic --
from ever contending with write locks on the primary.

If no replica URL is configured (e.g., local dev / tests), the replica
engine simply points at the same database as the primary -- correct
behavior, just without the read-scaling benefit.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

primary_engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_size=20)
replica_engine = create_async_engine(
    settings.database_replica_url or settings.database_url,
    pool_pre_ping=True,
    pool_size=20,
)

PrimarySession = async_sessionmaker(primary_engine, expire_on_commit=False)
ReplicaSession = async_sessionmaker(replica_engine, expire_on_commit=False)


async def get_primary_session() -> AsyncGenerator[AsyncSession, None]:
    async with PrimarySession() as session:
        yield session


async def get_replica_session() -> AsyncGenerator[AsyncSession, None]:
    async with ReplicaSession() as session:
        yield session
