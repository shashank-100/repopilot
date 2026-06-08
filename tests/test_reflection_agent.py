"""Tests for Phase 12: ReflectionAgent."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from repopilot.agents.reflection import ReflectionAgent, _ReflectionSchema
from repopilot.state_store import create_run, delete_run


def _state_with_failures(tmp_path):
    state = create_run("add rate limiting", str(tmp_path))
    state["validation_results"] = {
        "passed": False,
        "pytest_output": "FAILED tests/test_api.py::test_health - AssertionError",
        "mypy_output": "error: incompatible types",
        "ruff_output": "",
        "errors": ["pytest failed (rc=1)", "mypy reported type errors"],
    }
    state["execution_plan"] = {
        "goal": "add rate limiting",
        "steps": [
            {"id": "s1", "description": "create middleware.py",
             "tool_hints": [], "files_to_modify": [], "depends_on": [], "status": "failed"},
            {"id": "s2", "description": "register middleware",
             "tool_hints": [], "files_to_modify": [], "depends_on": [], "status": "pending"},
        ],
        "risks": [],
    }
    state["repair_attempts"] = 1
    return state


def _fake_reflection():
    return _ReflectionSchema(
        failure_summary="middleware.py had incorrect import",
        root_cause="Missing import for RateLimitMiddleware",
        plan_patches=[
            {"id": "s1", "description": "fix import in middleware.py", "status": "pending"},
        ],
        retry_strategy="Add missing import before registering middleware",
    )


def _patched_agent() -> ReflectionAgent:
    agent = ReflectionAgent.__new__(ReflectionAgent)
    agent._llm = MagicMock()
    return agent


def test_reflection_populates_report(tmp_path):
    state = _state_with_failures(tmp_path)
    agent = _patched_agent()
    agent._llm.with_structured_output.return_value.invoke.return_value = _fake_reflection()
    result = agent.run(state)

    report = result["reflection_report"]
    assert report["root_cause"] == "Missing import for RateLimitMiddleware"
    assert len(report["plan_patches"]) == 1
    assert report["plan_patches"][0]["status"] == "pending"
    delete_run(state["run_id"])


def test_reflection_sets_phase(tmp_path):
    state = _state_with_failures(tmp_path)
    agent = _patched_agent()
    agent._llm.with_structured_output.return_value.invoke.return_value = _fake_reflection()
    result = agent.run(state)

    assert result["current_phase"] == "reflection"
    delete_run(state["run_id"])


def test_observation_includes_root_cause(tmp_path):
    state = _state_with_failures(tmp_path)
    agent = _patched_agent()
    agent._llm.with_structured_output.return_value.invoke.return_value = _fake_reflection()
    result = agent.run(state)

    assert any("Missing import" in obs for obs in result["observations"])
    delete_run(state["run_id"])


def test_planning_agent_applies_patches(tmp_path):
    """Verify PlanningAgent.replan() picks up reflection patches correctly."""
    from repopilot.agents.planning import PlanningAgent

    state = _state_with_failures(tmp_path)
    state["reflection_report"] = {
        "failure_summary": "bad import",
        "root_cause": "missing import",
        "plan_patches": [{"id": "s1", "description": "fixed import", "status": "pending"}],
        "retry_strategy": "fix import",
    }

    result = PlanningAgent().replan(state, state["reflection_report"]["plan_patches"])
    patched = {s["id"]: s for s in result["execution_plan"]["steps"]}
    assert patched["s1"]["description"] == "fixed import"
    assert patched["s1"]["status"] == "pending"
    delete_run(state["run_id"])


def test_no_stubs_in_workflow():
    from repopilot.graph.workflow import build_graph
    g = build_graph(phases=["reflection"])
    assert "reflection" in list(g.get_graph().nodes)
