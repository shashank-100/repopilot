"""PostgreSQL-backed implementation of the state_store contract.

Used automatically by state_store.py when DATABASE_URL is set.

Each public function runs a self-contained async operation: it builds a fresh
engine, does the work, and disposes the engine — all inside one asyncio.run in
a dedicated worker thread. This avoids asyncpg's "connections can't cross event
loops" problem when called from sync code that may or may not already be inside
a running loop (e.g. FastAPI background tasks).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from repopilot.db.engine import _make_engine, get_database_url
from repopilot.db.models import RunRecord
from repopilot.errors import PersistenceError
from repopilot.state import RepoPilotState

T = TypeVar("T")


# ── serialisation ──────────────────────────────────────────────────────────────

def _to_json(state: RepoPilotState) -> str:
    snap = {k: v for k, v in state.items() if k != "repository_graph"}
    return json.dumps(snap, default=str)


def _from_json(raw: str) -> RepoPilotState:
    return json.loads(raw)  # type: ignore[return-value]


# ── run an operation against a fresh, disposable engine ─────────────────────────

async def _with_session(fn: Callable[[Any], Awaitable[T]]) -> T:
    eng = _make_engine(get_database_url() or "")
    try:
        maker = async_sessionmaker(eng, expire_on_commit=False)
        async with maker() as session:
            return await fn(session)
    finally:
        await eng.dispose()


def _run(fn: Callable[[Any], Awaitable[T]]) -> T:
    """Run an async session operation from any sync context, isolated in its own loop."""
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _with_session(fn)).result()
    except KeyError:
        raise  # not-found is a normal control-flow signal, preserve it
    except Exception as exc:  # noqa: BLE001 — boundary: classify DB failures
        raise PersistenceError(str(exc)) from exc


# ── sync public API (matches state_store contract) ─────────────────────────────

def create_run_db(objective: str, repo_path: str, state: RepoPilotState) -> None:
    async def op(session: Any) -> None:
        session.add(RunRecord(
            run_id=state["run_id"],
            objective=objective,
            repo_path=repo_path,
            current_phase=state["current_phase"],
            state_json=_to_json(state),
        ))
        await session.commit()
    _run(op)


def get_run_db(run_id: str) -> RepoPilotState:
    async def op(session: Any) -> RepoPilotState:
        row = await session.get(RunRecord, run_id)
        if row is None:
            raise KeyError(f"run {run_id!r} not found")
        return _from_json(row.state_json)
    return _run(op)


def update_run_db(state: RepoPilotState) -> None:
    async def op(session: Any) -> None:
        await session.execute(
            update(RunRecord)
            .where(RunRecord.run_id == state["run_id"])
            .values(
                current_phase=state.get("current_phase", "created"),
                state_json=_to_json(state),
            )
        )
        await session.commit()
    _run(op)


def list_runs_db() -> list[str]:
    async def op(session: Any) -> list[str]:
        result = await session.execute(
            select(RunRecord.run_id).order_by(RunRecord.created_at.desc())
        )
        return list(result.scalars())
    return _run(op)


def delete_run_db(run_id: str) -> None:
    async def op(session: Any) -> None:
        await session.execute(delete(RunRecord).where(RunRecord.run_id == run_id))
        await session.commit()
    _run(op)
