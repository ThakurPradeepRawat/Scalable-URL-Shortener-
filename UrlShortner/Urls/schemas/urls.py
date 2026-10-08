from datetime import datetime, timezone
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LongUrlRequest(BaseModel):
    long_url: str = Field(min_length=1, max_length=2048)
    expires_at: datetime | None = None

    @field_validator("long_url")
    @classmethod
    def validate_long_url(cls, value: str) -> str:
        if any(character.isspace() or ord(character) < 33 for character in value):
            raise ValueError("long_url cannot contain whitespace or control characters")
        try:
            parsed = urlsplit(value)
            hostname = parsed.hostname
            parsed.port
        except ValueError as error:
            raise ValueError("long_url must be a valid HTTP or HTTPS URL") from error
        if parsed.scheme not in {"http", "https"} or not hostname:
            raise ValueError("long_url must be a valid HTTP or HTTPS URL")
        return value

    @field_validator("expires_at")
    @classmethod
    def validate_expiration(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        if value <= datetime.now(timezone.utc):
            raise ValueError("expires_at must be in the future")
        return value


class LongUrlResponse(BaseModel):
    short_code: str
    short_url: str
    created_at: datetime
    expires_at: datetime | None


class GetUrlRequest(BaseModel):
    short_code: str


class GetUrlResponse(BaseModel):
    short_code: str
    long_url: str
    created_at: datetime
    expires_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DeleteUrlRequest(BaseModel):
    short_code: str


class DeleteUrlResponse(BaseModel):
    message: str
