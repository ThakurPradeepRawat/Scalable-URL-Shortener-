from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_client import set_cached_url
from app.core.base62 import encode
from app.core.config import get_settings
from app.db.models import ShortURL
from app.db.session import get_primary_session
from app.schemas import ShortenRequest, ShortenResponse

router = APIRouter(tags=["shorten"])
settings = get_settings()


@router.post("/api/shorten", response_model=ShortenResponse, status_code=status.HTTP_201_CREATED)
async def create_short_url(
    payload: ShortenRequest,
    request: Request,
    session: AsyncSession = Depends(get_primary_session),
) -> ShortenResponse:
    expires_at = None
    if payload.ttl_seconds:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=payload.ttl_seconds)

    # The distributed block allocator is the single source of unique
    # integer IDs in the system. It's used as the row's primary key
    # *and*, when no custom alias is given, Base62-encoded into the
    # public short_code -- one allocation covers both, and the row's
    # own primary key is never left to implicit DB autoincrement
    # (which doesn't reliably apply to a BigInteger PK across backends).
    allocator = request.app.state.id_allocator
    new_id = await allocator.allocate_id(session)
    short_code = payload.custom_alias or encode(new_id, min_length=settings.short_code_min_length)

    record = ShortURL(
        id=new_id,
        short_code=short_code,
        long_url=payload.long_url,
        expires_at=expires_at,
    )
    session.add(record)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"short_code '{short_code}' is already taken",
        )

    # Write-through: the first redirect for this (possibly viral) link
    # is a cache hit, not a guaranteed miss.
    await set_cached_url(short_code, payload.long_url, ttl_seconds=payload.ttl_seconds)

    return ShortenResponse(
        short_url=f"https://{settings.base_domain}/{short_code}",
        short_code=short_code,
        long_url=payload.long_url,
        expires_at=expires_at,
    )
