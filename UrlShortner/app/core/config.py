"""
Centralized application configuration, loaded from environment variables.

Using pydantic-settings means every config value is validated and typed
at startup — a malformed DATABASE_URL fails fast at boot, not on the
first request that happens to touch the DB.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # -- Database --
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/urls"
    database_replica_url: str | None = None  # falls back to primary if unset

    # -- Redis --
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 days default hot-cache TTL

    # -- Short code generation --
    base_domain: str = "psbe.io"
    id_block_size: int = 10_000  # IDs pre-allocated per app instance per DB round trip
    short_code_min_length: int = 6

    # -- Rate limiting (token bucket) --
    rate_limit_capacity: int = 20       # max burst size
    rate_limit_refill_per_sec: float = 10.0  # steady-state requests/sec allowed

    # -- Misc --
    default_ttl_seconds: int | None = None  # None = URLs never expire unless specified
    click_flush_interval_seconds: int = 5   # how often buffered clicks are flushed to Postgres


@lru_cache
def get_settings() -> Settings:
    return Settings()
