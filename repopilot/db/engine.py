"""Async SQLAlchemy engine — created lazily on first use."""
from __future__ import annotations

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    pass


def get_database_url() -> str | None:
    return os.getenv("DATABASE_URL")


def _make_engine(url: str) -> AsyncEngine:
    # Convert postgres:// → postgresql+asyncpg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # asyncpg doesn't accept libpq's ?sslmode= query param; strip it and
    # pass ssl via connect_args instead. Managed Postgres (Supabase, etc.)
    # requires TLS, so default to ssl=True when host is not local.
    connect_args: dict[str, object] = {}
    if "sslmode=" in url:
        import re
        url = re.sub(r"[?&]sslmode=[^&]*", "", url)
    if "localhost" not in url and "127.0.0.1" not in url:
        # Managed Postgres (Supabase) presents a chain Python doesn't trust by
        # default. Use an encrypted-but-unverified context — the host is fixed
        # in DATABASE_URL so MITM risk is acceptable for this connection.
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ctx

    return create_async_engine(
        url, pool_pre_ping=True, echo=False, connect_args=connect_args
    )


def engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = get_database_url()
        if not url:
            raise RuntimeError("DATABASE_URL not set")
        _engine = _make_engine(url)
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory()() as session:
        yield session
