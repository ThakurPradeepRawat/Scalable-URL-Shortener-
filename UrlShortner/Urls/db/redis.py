from typing import Any

from redis import Redis
from starlette.requests import Request

from core.config import settings


def create_redis_client() -> Redis:
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


def get_redis(request: Request) -> Any:
    return request.app.state.redis