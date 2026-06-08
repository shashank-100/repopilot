from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from repopilot.api.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from repopilot.api.routers import health, runs
from repopilot.observability import configure_logging, configure_tracing

logger = structlog.get_logger(__name__)
_STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    configure_tracing()
    import os
    if os.getenv("DATABASE_URL"):
        # Don't let a slow/unreachable DB block startup — the app should still
        # serve /health so the platform's healthcheck passes. Runs init in the
        # background with a timeout; falls back to in-memory if it fails.
        import asyncio

        async def _try_init_db() -> None:
            try:
                from repopilot.db.init_db import init_db_async
                await asyncio.wait_for(init_db_async(), timeout=20)
                logger.info("repopilot.db.ready")
            except Exception as exc:  # noqa: BLE001
                logger.warning("repopilot.db.init_failed", error=str(exc))

        asyncio.create_task(_try_init_db())
    logger.info("repopilot.startup", version="0.1.0")
    yield
    logger.info("repopilot.shutdown")


app = FastAPI(title="RepoPilot", version="0.1.0", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(runs.router)


@app.get("/repos")
async def list_repos() -> dict[str, list[dict[str, str]]]:
    """List GitHub repos the agent can open PRs on (App installations / PAT)."""
    import asyncio

    from repopilot.github_auth import list_accessible_repos
    repos = await asyncio.to_thread(list_accessible_repos)
    return {"repos": sorted(repos, key=lambda r: r["full_name"].lower())}


@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
