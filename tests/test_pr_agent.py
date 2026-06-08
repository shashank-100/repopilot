"""Tests for Phase 14: PRAgent."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from repopilot.agents.pr_generation import PRAgent, _PRSchema
from repopilot.state_store import create_run, delete_run


def _make_state(tmp_path, passed=True):
    state = create_run("add rate limiting middleware", str(tmp_path))
    state["modified_files"] = [str(tmp_path / "middleware.py"), str(tmp_path / "main.py")]
    state["validation_results"] = {
        "severity": "pass" if passed else "warnings",
        "validated_with": "tests",
        "passed": passed,
        "summary": "Validated via tests — clean" if passed else "Validated via tests — 1 finding",
        "pytest_output": "5 passed",
        "mypy_output": "Success",
        "ruff_output": "",
        "findings": [] if passed else ["pytest failed"],
        "errors": [] if passed else ["pytest failed"],
    }
    state["execution_plan"] = {
        "goal": "add rate limiting",
        "steps": [
            {"id": "s1", "description": "create middleware", "status": "done",
             "tool_hints": [], "files_to_modify": [], "depends_on": []},
            {"id": "s2", "description": "register middleware", "status": "done",
             "tool_hints": [], "files_to_modify": [], "depends_on": []},
        ],
        "risks": [],
        "migration_notes": ["middleware.py: added RateLimitMiddleware class"],
    }
    state["repository_map"] = {
        "root_path": str(tmp_path), "framework": "fastapi",
        "language": "python", "key_files": [], "entry_points": [],
        "test_dirs": [], "config_files": [], "summary": "FastAPI service",
    }
    state["repair_attempts"] = 0
    return state


def _fake_pr():
    return _PRSchema(
        title="feat: add rate limiting middleware",
        summary="Adds SlowAPI-based rate limiting to all API routes.",
        changes=["Added middleware.py with RateLimitMiddleware", "Registered middleware in main.py"],
        tests_executed=["pytest", "mypy", "ruff"],
        risks=["Rate limits may affect existing clients"],
        rollback_plan="Revert middleware.py and remove registration from main.py",
    )


def _patched_agent() -> PRAgent:
    """Return a PRAgent whose LLM is a plain MagicMock (not a frozen Pydantic model)."""
    agent = PRAgent.__new__(PRAgent)
    agent._llm = MagicMock()
    return agent


def test_pr_populated(tmp_path):
    state = _make_state(tmp_path)
    agent = _patched_agent()
    agent._llm.with_structured_output.return_value.invoke.return_value = _fake_pr()
    result = agent.run(state)

    pr = result["generated_pr"]
    assert pr["title"] == "feat: add rate limiting middleware"
    assert len(pr["changes"]) == 2
    assert pr["rollback_plan"] != ""
    delete_run(state["run_id"])


def test_pr_sets_phase(tmp_path):
    state = _make_state(tmp_path)
    agent = _patched_agent()
    agent._llm.with_structured_output.return_value.invoke.return_value = _fake_pr()
    result = agent.run(state)

    assert result["current_phase"] == "pr_generation"
    delete_run(state["run_id"])


def test_tests_executed_includes_standard_suite(tmp_path):
    state = _make_state(tmp_path)
    agent = _patched_agent()
    agent._llm.with_structured_output.return_value.invoke.return_value = _fake_pr()
    result = agent.run(state)

    assert "Ran the repository test suite" in result["generated_pr"]["tests_executed"]
    delete_run(state["run_id"])


def test_observation_includes_title(tmp_path):
    state = _make_state(tmp_path)
    agent = _patched_agent()
    agent._llm.with_structured_output.return_value.invoke.return_value = _fake_pr()
    result = agent.run(state)

    assert any("rate limiting" in obs for obs in result["observations"])
    delete_run(state["run_id"])


def test_failed_validation_does_not_block_pr(tmp_path):
    state = _make_state(tmp_path, passed=False)
    agent = _patched_agent()
    agent._llm.with_structured_output.return_value.invoke.return_value = _fake_pr()
    result = agent.run(state)

    assert "generated_pr" in result
    delete_run(state["run_id"])


def test_no_stubs_in_workflow():
    from repopilot.graph.workflow import build_graph
    g = build_graph(phases=["pr_generation"])
    assert "pr_generation" in list(g.get_graph().nodes)
