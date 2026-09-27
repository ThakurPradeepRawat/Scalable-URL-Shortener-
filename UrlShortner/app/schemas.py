import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_CUSTOM_ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,16}$")


class ShortenRequest(BaseModel):
    long_url: str = Field(..., min_length=1, max_length=8192)
    custom_alias: str | None = Field(default=None)
    ttl_seconds: int | None = Field(default=None, ge=60, le=60 * 60 * 24 * 365)

    @field_validator("long_url")
    @classmethod
    def must_look_like_a_url(cls, value: str) -> str:
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("long_url must start with http:// or https://")
        return value

    @field_validator("custom_alias")
    @classmethod
    def alias_must_be_url_safe(cls, value: str | None) -> str | None:
        if value is not None and not _CUSTOM_ALIAS_PATTERN.match(value):
            raise ValueError(
                "custom_alias must be 3-16 characters of letters, digits, '-' or '_'"
            )
        return value


class ShortenResponse(BaseModel):
    short_url: str
    short_code: str
    long_url: str
    expires_at: datetime | None = None


class StatsResponse(BaseModel):
    short_code: str
    long_url: str
    clicks: int
    created_at: datetime
    expires_at: datetime | None = None
