"""State store — transparent in-memory or PostgreSQL backend.

When DATABASE_URL is set the module delegates to repopilot.db.store (async
SQLAlchemy + asyncpg). Otherwise it falls back to the in-memory dict.
The public API is identical in both cases so no other module needs to change.
"""
from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

from repopilot.state import RepoPilotState

# ── in-memory fallback ────────────────────────────────────────────────────────

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
    if _USE_DB:
        create_run_db(objective, repo_path, state)
    else:
        _store[run_id] = state
    return state


def get_run(run_id: str) -> RepoPilotState:
    if _USE_DB:
        return get_run_db(run_id)
    if run_id not in _store:
        raise KeyError(f"run {run_id!r} not found")
    return _store[run_id]


def update_run(state: RepoPilotState) -> None:
    if _USE_DB:
        update_run_db(state)
    else:
        _store[state["run_id"]] = state


def list_runs(self=None) -> list[str] | "KeysView[str]":  # type: ignore[return]
    if _USE_DB:
        return list_runs_db()
    return _store.keys()


def delete_run(run_id: str) -> None:
    if _USE_DB:
        delete_run_db(run_id)
    else:
        _store.pop(run_id, None)
