from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.dependencies import get_short_url_service
from core.config import settings
from schemas.urls import DeleteUrlResponse, GetUrlResponse, LongUrlRequest, LongUrlResponse
from service.urls import (
    CounterUnavailableError,
    ShortUrlNotFoundError,
    shortUrlService,
)

router = APIRouter(prefix="/urls/v1")


@router.post("/", response_model=LongUrlResponse, status_code=status.HTTP_201_CREATED)
def make_short(data: LongUrlRequest, service: shortUrlService = Depends(get_short_url_service)):
    try:
        record = service.create_short_url(data)
    except CounterUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return LongUrlResponse(
        short_code=record.short_code,
        short_url=f"{settings.public_base_url}/r/{record.short_code}",
        created_at=record.created_at,
        expires_at=record.expires_at,
    )


@router.get("/{short_code}", response_model=GetUrlResponse)
def get_short(short_code: str, service: shortUrlService = Depends(get_short_url_service)):
    try:
        return service.get_short_url(short_code)
    except ShortUrlNotFoundError as error:
        raise HTTPException(status_code=404, detail="Short URL not found") from error


@router.delete("/{short_code}", response_model=DeleteUrlResponse)
def delete_url(short_code: str, service: shortUrlService = Depends(get_short_url_service)):
    if not service.delete_short_url(short_code):
        raise HTTPException(status_code=404, detail="Short URL not found")
    return DeleteUrlResponse(message="Short URL deactivated")
