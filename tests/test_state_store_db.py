"""Tests for Phase 15: state_store interface contract.

These tests run against the in-memory backend (no DATABASE_URL set).
They verify that state_store.py's public API still works correctly after
the refactor and that _USE_DB is False in the test environment.
"""
import os
import pytest
from repopilot import state_store


def test_uses_memory_in_tests():
    assert not state_store._USE_DB, "DATABASE_URL must not be set in test environment"


def test_create_and_get(tmp_path):
    s = state_store.create_run("test objective", str(tmp_path))
    retrieved = state_store.get_run(s["run_id"])
    assert retrieved["objective"] == "test objective"
    assert retrieved["repo_path"] == str(tmp_path)
    assert retrieved["current_phase"] == "created"
    state_store.delete_run(s["run_id"])


def test_update_persists(tmp_path):
    s = state_store.create_run("update test", str(tmp_path))
    s["current_phase"] = "planning"
    s["observations"].append("step done")
    state_store.update_run(s)
    fresh = state_store.get_run(s["run_id"])
    assert fresh["current_phase"] == "planning"
    assert "step done" in fresh["observations"]
    state_store.delete_run(s["run_id"])


def test_list_contains_created(tmp_path):
    s = state_store.create_run("list test", str(tmp_path))
    assert s["run_id"] in list(state_store.list_runs())
    state_store.delete_run(s["run_id"])


def test_delete_removes(tmp_path):
    s = state_store.create_run("delete test", str(tmp_path))
    state_store.delete_run(s["run_id"])
    with pytest.raises(KeyError):
        state_store.get_run(s["run_id"])


def test_missing_run_raises():
    with pytest.raises(KeyError):
        state_store.get_run("00000000-0000-0000-0000-000000000000")


def test_full_state_roundtrip(tmp_path):
    """All RepoPilotState fields survive a create→update→get cycle."""
    s = state_store.create_run("roundtrip", str(tmp_path))
    s["tool_history"].append({
        "tool_name": "fs.read_file", "args": {"path": "/tmp/f.py"},
        "result": {"content": "x=1"}, "success": True,
        "timestamp": "2026-01-01T00:00:00Z", "duration_ms": 12.3,
    })
    s["modified_files"].append("/tmp/f.py")
    s["repair_attempts"] = 2
    s["generated_pr"] = {
        "title": "feat: test", "summary": "...", "changes": ["a"],
        "tests_executed": ["pytest"], "risks": [], "rollback_plan": "revert",
    }
    state_store.update_run(s)
    fresh = state_store.get_run(s["run_id"])
    assert len(fresh["tool_history"]) == 1
    assert fresh["tool_history"][0]["tool_name"] == "fs.read_file"
    assert fresh["repair_attempts"] == 2
    assert fresh["generated_pr"]["title"] == "feat: test"
    state_store.delete_run(s["run_id"])


def test_db_models_importable():
    """ORM models import cleanly without a live DB."""
    from repopilot.db import models
    from repopilot.db.engine import Base
    assert "runs" in Base.metadata.tables


def test_serialisation_excludes_graph(tmp_path):
    """state_json must not contain repository_graph (not JSON-serialisable)."""
    import json
    from repopilot.db.store import _to_json
    s = state_store.create_run("graph test", str(tmp_path))
    import networkx as nx
    s["repository_graph"] = nx.DiGraph()  # type: ignore[assignment]
    raw = _to_json(s)
    data = json.loads(raw)
    assert "repository_graph" not in data
    state_store.delete_run(s["run_id"])
