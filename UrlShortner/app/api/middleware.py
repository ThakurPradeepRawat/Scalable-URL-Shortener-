from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Second layer of rate limiting (first is Nginx's coarse IP-based
    `limit_req_zone`). This layer is per-client (by API key if present,
    else by IP) and uses the atomic Redis token bucket so bursts are
    tolerated but sustained abuse is rejected with 429.
    """

    async def dispatch(self, request: Request, call_next):
        limiter = getattr(request.app.state, "rate_limiter", None)
        if limiter is None:
            # Rate limiter not wired up (e.g., in unit tests) -- skip.
            return await call_next(request)

        client_id = request.headers.get("x-api-key") or (
            request.client.host if request.client else "unknown"
        )
        result = await limiter.allow(client_id)

        if not result.allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please slow down."},
            )

        return await call_next(request)
