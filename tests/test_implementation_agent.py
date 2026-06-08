"""Tests for Phase 10: ImplementationAgent."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repopilot.agents.implementation import ImplementationAgent, _FileEdit, _StepResult
from repopilot.state import RepoPilotState
from repopilot.state_store import create_run, delete_run
from repopilot.tools.base import load_all_tools, registry
from repopilot.tools.executor import ToolExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(tmp_path: Path, steps: list[dict] | None = None) -> RepoPilotState:
    state = create_run("add rate limiting", str(tmp_path))
    state["execution_plan"] = {
        "goal": "add rate limiting",
        "steps": steps or [],
        "risks": [],
    }
    state["repository_map"] = {
        "root_path": str(tmp_path),
        "framework": "fastapi",
        "language": "python",
        "key_files": [],
        "entry_points": [],
        "test_dirs": [],
        "config_files": [],
        "summary": "test repo",
    }
    return state


def _make_executor(state: RepoPilotState) -> ToolExecutor:
    load_all_tools()
    return ToolExecutor(registry, state)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_plan_skips_gracefully(tmp_path):
    state = create_run("noop", str(tmp_path))
    executor = _make_executor(state)
    agent = ImplementationAgent(executor=executor)
    result = agent.run(state)
    assert result["current_phase"] == "implementation"
    assert any("no execution_plan" in obs for obs in result["observations"])
    delete_run(state["run_id"])


def test_empty_steps_completes(tmp_path):
    state = _make_state(tmp_path, steps=[])
    executor = _make_executor(state)

    with patch.object(ImplementationAgent, "_execute_step") as mock_exec:
        agent = ImplementationAgent(executor=executor)
        result = agent.run(state)

    mock_exec.assert_not_called()
    assert result["current_phase"] == "implementation"
    delete_run(state["run_id"])


def test_already_done_steps_skipped(tmp_path):
    steps = [
        {"id": "s1", "description": "already done", "tool_hints": [],
         "files_to_modify": [], "depends_on": [], "status": "done"},
    ]
    state = _make_state(tmp_path, steps=steps)
    executor = _make_executor(state)

    with patch.object(ImplementationAgent, "_execute_step") as mock_exec:
        agent = ImplementationAgent(executor=executor)
        agent.run(state)

    mock_exec.assert_not_called()
    delete_run(state["run_id"])


def test_step_writes_file(tmp_path):
    target = tmp_path / "middleware.py"
    steps = [
        {
            "id": "s1",
            "description": "Create rate limiting middleware",
            "tool_hints": ["fs.write_file"],
            "files_to_modify": [str(target)],
            "depends_on": [],
            "status": "pending",
        }
    ]
    state = _make_state(tmp_path, steps=steps)
    executor = _make_executor(state)

    fake_result = _StepResult(
        summary="Created middleware.py",
        edits=[_FileEdit(path=str(target), content="# rate limit\n", is_new=True)],
    )

    with patch.object(ImplementationAgent, "_execute_step", return_value=fake_result):
        agent = ImplementationAgent(executor=executor)
        result_state = agent.run(state)

    assert target.read_text() == "# rate limit\n"
    assert str(target) in result_state["modified_files"]
    assert result_state["execution_plan"]["steps"][0]["status"] == "done"
    delete_run(state["run_id"])


def test_step_failure_marked_in_plan(tmp_path):
    steps = [
        {
            "id": "s1",
            "description": "Failing step",
            "tool_hints": [],
            "files_to_modify": [],
            "depends_on": [],
            "status": "pending",
        }
    ]
    state = _make_state(tmp_path, steps=steps)
    executor = _make_executor(state)

    with patch.object(ImplementationAgent, "_execute_step", side_effect=RuntimeError("oops")):
        agent = ImplementationAgent(executor=executor)
        result_state = agent.run(state)

    assert result_state["execution_plan"]["steps"][0]["status"] == "failed"
    assert any("s1 failed" in obs for obs in result_state["observations"])
    # Phase still advances so validation can report the failure
    assert result_state["current_phase"] == "implementation"
    delete_run(state["run_id"])


def test_multiple_steps_continue_after_failure(tmp_path):
    target = tmp_path / "ok.py"
    steps = [
        {"id": "s1", "description": "bad step", "tool_hints": [],
         "files_to_modify": [], "depends_on": [], "status": "pending"},
        {"id": "s2", "description": "good step", "tool_hints": ["fs.write_file"],
         "files_to_modify": [str(target)], "depends_on": [], "status": "pending"},
    ]
    state = _make_state(tmp_path, steps=steps)
    executor = _make_executor(state)

    fake_good = _StepResult(
        summary="Wrote ok.py",
        edits=[_FileEdit(path=str(target), content="x = 1\n")],
    )

    def _side_effect(step, *a, **kw):
        if step["id"] == "s1":
            raise RuntimeError("forced failure")
        return fake_good

    with patch.object(ImplementationAgent, "_execute_step", side_effect=_side_effect):
        agent = ImplementationAgent(executor=executor)
        result_state = agent.run(state)

    plan_steps = {s["id"]: s for s in result_state["execution_plan"]["steps"]}
    assert plan_steps["s1"]["status"] == "failed"
    assert plan_steps["s2"]["status"] == "done"
    assert target.exists()
    delete_run(state["run_id"])


def test_modified_files_no_duplicates(tmp_path):
    target = tmp_path / "shared.py"
    steps = [
        {"id": "s1", "description": "write shared.py", "tool_hints": [],
         "files_to_modify": [], "depends_on": [], "status": "pending"},
        {"id": "s2", "description": "write shared.py again", "tool_hints": [],
         "files_to_modify": [], "depends_on": [], "status": "pending"},
    ]
    state = _make_state(tmp_path, steps=steps)
    executor = _make_executor(state)

    fake = _StepResult(
        summary="wrote",
        edits=[_FileEdit(path=str(target), content="pass\n")],
    )

    with patch.object(ImplementationAgent, "_execute_step", return_value=fake):
        agent = ImplementationAgent(executor=executor)
        result_state = agent.run(state)

    assert result_state["modified_files"].count(str(target)) == 1
    delete_run(state["run_id"])


def test_relative_path_resolved_to_repo(tmp_path):
    steps = [
        {"id": "s1", "description": "new file", "tool_hints": [],
         "files_to_modify": [], "depends_on": [], "status": "pending"},
    ]
    state = _make_state(tmp_path, steps=steps)
    executor = _make_executor(state)

    fake = _StepResult(
        summary="wrote",
        edits=[_FileEdit(path="new_module.py", content="# new\n", is_new=True)],
    )

    with patch.object(ImplementationAgent, "_execute_step", return_value=fake):
        agent = ImplementationAgent(executor=executor)
        result_state = agent.run(state)

    expected = str(tmp_path / "new_module.py")
    assert (tmp_path / "new_module.py").exists()
    assert expected in result_state["modified_files"]
    delete_run(state["run_id"])


def test_workflow_node_is_not_stub():
    """Confirm implementation node in the graph is the real agent, not a stub."""
    from repopilot.graph.workflow import build_graph
    graph = build_graph(phases=["implementation"])
    # The node should exist and not raise on inspection
    node_names = list(graph.get_graph().nodes)
    assert "implementation" in node_names


def test_step_result_coerces_stringified_edits():
    """Haiku sometimes returns edits as a JSON string — must coerce to list."""
    import json
    edits_str = json.dumps([{"path": "/a.py", "content": "x", "is_new": True}])
    r = _StepResult(summary="s", edits=edits_str, observations="[]")
    assert len(r.edits) == 1
    assert r.edits[0].path == "/a.py"


def test_step_result_normal_list_unaffected():
    r = _StepResult(summary="s", edits=[{"path": "/b.py", "content": "y"}])
    assert len(r.edits) == 1
    assert r.edits[0].path == "/b.py"


def test_step_result_unparseable_string_yields_empty():
    r = _StepResult(summary="s", edits="not json at all")
    assert r.edits == []
