"""Tests for Phase 11: ValidationAgent."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repopilot.agents.validation import ValidationAgent
from repopilot.state_store import create_run, delete_run
from repopilot.tools.base import ToolOutput


def _mock_executor(pytest_pass=True, mypy_pass=True, ruff_pass=True):
    executor = MagicMock()

    def run(tool_name, **kwargs):
        if tool_name == "terminal.run_pytest":
            return ToolOutput(
                success=pytest_pass,
                data={"returncode": 0 if pytest_pass else 1,
                      "stdout": "3 passed" if pytest_pass else "1 failed",
                      "stderr": ""},
            )
        if tool_name == "terminal.run_mypy":
            return ToolOutput(
                success=mypy_pass,
                data={"returncode": 0 if mypy_pass else 1,
                      "stdout": "Success" if mypy_pass else "error: type mismatch",
                      "stderr": ""},
            )
        if tool_name == "terminal.run_ruff":
            return ToolOutput(
                success=ruff_pass,
                data={"returncode": 0 if ruff_pass else 1,
                      "stdout": "" if ruff_pass else "E501 line too long",
                      "stderr": ""},
            )
        return ToolOutput(success=True, data={})

    executor.run.side_effect = run
    return executor


def test_all_pass(tmp_path):
    state = create_run("test", str(tmp_path))
    agent = ValidationAgent(executor=_mock_executor())
    result = agent.run(state)

    assert result["current_phase"] == "validation"
    assert result["validation_results"]["passed"] is True
    assert result["validation_results"]["errors"] == []
    assert any("passed" in obs for obs in result["observations"])
    delete_run(state["run_id"])


def test_pytest_fail(tmp_path):
    state = create_run("test", str(tmp_path))
    agent = ValidationAgent(executor=_mock_executor(pytest_pass=False))
    result = agent.run(state)

    assert result["validation_results"]["passed"] is False
    assert any("pytest" in e for e in result["validation_results"]["errors"])
    delete_run(state["run_id"])


def test_mypy_and_ruff_fail(tmp_path):
    # mypy/ruff only run when the repo configures them
    (tmp_path / "pyproject.toml").write_text(
        "[tool.mypy]\nstrict = true\n\n[tool.ruff]\nline-length = 100\n"
    )
    state = create_run("test", str(tmp_path))
    agent = ValidationAgent(executor=_mock_executor(mypy_pass=False, ruff_pass=False))
    result = agent.run(state)

    assert result["validation_results"]["passed"] is False
    errors = result["validation_results"]["errors"]
    assert len(errors) == 2
    delete_run(state["run_id"])


def test_mypy_ruff_skipped_without_config(tmp_path):
    # No pyproject.toml → mypy/ruff are skipped → only pytest matters
    state = create_run("test", str(tmp_path))
    agent = ValidationAgent(executor=_mock_executor(mypy_pass=False, ruff_pass=False))
    result = agent.run(state)
    # mypy/ruff skipped, pytest passed → overall passed
    assert result["validation_results"]["passed"] is True
    delete_run(state["run_id"])


def test_outputs_captured(tmp_path):
    state = create_run("test", str(tmp_path))
    agent = ValidationAgent(executor=_mock_executor(pytest_pass=False))
    result = agent.run(state)

    assert "failed" in result["validation_results"]["pytest_output"]
    delete_run(state["run_id"])


def test_no_stubs_in_workflow():
    from repopilot.graph.workflow import build_graph
    g = build_graph(phases=["validation"])
    nodes = list(g.get_graph().nodes)
    assert "validation" in nodes
