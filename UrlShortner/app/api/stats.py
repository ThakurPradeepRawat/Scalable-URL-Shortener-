from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ShortURL
from app.db.session import get_replica_session
from app.schemas import StatsResponse

router = APIRouter(tags=["stats"])


@router.get("/api/stats/{short_code}", response_model=StatsResponse)
async def get_stats(
    short_code: str,
    session: AsyncSession = Depends(get_replica_session),
) -> StatsResponse:
    result = await session.execute(select(ShortURL).where(ShortURL.short_code == short_code))
    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found")

    return StatsResponse(
        short_code=record.short_code,
        long_url=record.long_url,
        clicks=record.click_count,
        created_at=record.created_at,
        expires_at=record.expires_at,
    )
