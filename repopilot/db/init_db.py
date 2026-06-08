"""Create all tables. Called at app startup when DATABASE_URL is set."""
from __future__ import annotations

import asyncio

from repopilot.db.engine import Base, engine
from repopilot.db import models  # noqa: F401 — registers ORM models


async def init_db_async() -> None:
    """Create tables. Use from inside an event loop (e.g. FastAPI lifespan)."""
    async with engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_db() -> None:
    """Create tables from a sync context (e.g. a script)."""
    asyncio.run(init_db_async())
