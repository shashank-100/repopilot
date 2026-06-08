"""State store — PostgreSQL with transparent in-memory fallback.

When DATABASE_URL is set the store writes through to PostgreSQL (via
repopilot.db.store). Every run is ALSO mirrored in an in-memory dict, so if a
DB operation fails (e.g. the database is unreachable from this host) the API
degrades gracefully to in-memory instead of returning 500s. Without
DATABASE_URL it is purely in-memory.

The public API is identical in all cases so no other module needs to change.
"""
from __future__ import annotations

import os
import uuid

import structlog

from repopilot.errors import PersistenceError
from repopilot.state import RepoPilotState

logger = structlog.get_logger(__name__)

# In-memory mirror — always populated, used as the fallback path.
_store: dict[str, RepoPilotState] = {}

_USE_DB = bool(os.getenv("DATABASE_URL"))

if _USE_DB:
    from repopilot.db.store import (
        create_run_db,
        delete_run_db,
        get_run_db,
        list_runs_db,
        update_run_db,
    )


# ── public API ────────────────────────────────────────────────────────────────

def create_run(objective: str, repo_path: str) -> RepoPilotState:
    run_id = str(uuid.uuid4())
    state: RepoPilotState = {
        "run_id": run_id,
        "objective": objective,
        "repo_path": repo_path,
        "tool_history": [],
        "observations": [],
        "modified_files": [],
        "repair_attempts": 0,
        "current_phase": "created",
    }
    _store[run_id] = state  # always mirror in memory
    if _USE_DB:
        try:
            create_run_db(objective, repo_path, state)
        except PersistenceError as exc:
            logger.warning("state_store.db_fallback", op="create", error=str(exc))
    return state


def get_run(run_id: str) -> RepoPilotState:
    if _USE_DB:
        try:
            return get_run_db(run_id)
        except KeyError:
            raise
        except PersistenceError as exc:
            logger.warning("state_store.db_fallback", op="get", error=str(exc))
    if run_id not in _store:
        raise KeyError(f"run {run_id!r} not found")
    return _store[run_id]


def update_run(state: RepoPilotState) -> None:
    _store[state["run_id"]] = state  # always mirror
    if _USE_DB:
        try:
            update_run_db(state)
        except PersistenceError as exc:
            logger.warning("state_store.db_fallback", op="update", error=str(exc))


def list_runs() -> list[str]:
    if _USE_DB:
        try:
            return list_runs_db()
        except PersistenceError as exc:
            logger.warning("state_store.db_fallback", op="list", error=str(exc))
    return list(_store.keys())


def delete_run(run_id: str) -> None:
    _store.pop(run_id, None)
    if _USE_DB:
        try:
            delete_run_db(run_id)
        except PersistenceError as exc:
            logger.warning("state_store.db_fallback", op="delete", error=str(exc))
