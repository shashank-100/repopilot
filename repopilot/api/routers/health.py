"""Router for /health endpoint."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from repopilot.api.middleware.rate_limit import limiter

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
@limiter.limit("120/minute")
async def health_check(request: Request) -> HealthResponse:
    """Liveness / readiness probe.

    Rate limit: 120 requests per minute per IP.
    """
    return HealthResponse(status="ok", version="0.1.0")
