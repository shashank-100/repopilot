"""Rate limiting configuration using slowapi.

Provides a shared Limiter instance and a 429 exception handler.

Per-route limits (applied via @limiter.limit decorators):
  POST /runs                 : 10/minute
  GET  /runs                 : 60/minute
  GET  /runs/{run_id}        : 60/minute
  GET  /health               : 120/minute
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

__all__ = ["limiter", "rate_limit_exceeded_handler"]

limiter: Limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return 429 when a rate limit is exceeded."""
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
        headers={"Retry-After": "60"},
    )
