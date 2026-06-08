"""Tests for Phase 16: Evaluation framework."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repopilot.evaluation.metrics import SuiteMetrics, TaskMetrics
from repopilot.evaluation.tasks import (
    DEFAULT_TASKS,
    EvalTask,
    has_pr,
    modified_files_gt,
    no_error,
    plan_has_steps,
    reached_phase,
    validation_passed,
)
from repopilot.state_store import create_run


# ─── criterion helpers ────────────────────────────────────────────────────────

def _make_state(tmp_path, phase="pr_generation", **overrides):
    s = create_run("test", str(tmp_path))
    s["current_phase"] = phase
    for k, v in overrides.items():
        s[k] = v  # type: ignore[literal-required]
    return s


def test_reached_phase(tmp_path):
    s = _make_state(tmp_path, phase="planning")
    assert reached_phase("planning")(s)
    assert not reached_phase("pr_generation")(s)


def test_no_error(tmp_path):
    s = _make_state(tmp_path, phase="pr_generation")
    assert no_error()(s)
    s["current_phase"] = "error"
    assert not no_error()(s)


def test_has_pr(tmp_path):
    s = _make_state(tmp_path)
    assert not has_pr()(s)
    s["generated_pr"] = {  # type: ignore[typeddict-unknown-key]
        "title": "t", "summary": "s", "changes": [],
        "tests_executed": [], "risks": [], "rollback_plan": "",
    }
    assert has_pr()(s)


def test_modified_files_gt(tmp_path):
    s = _make_state(tmp_path)
    assert not modified_files_gt(0)(s)
    s["modified_files"].append("/tmp/x.py")
    assert modified_files_gt(0)(s)
    assert not modified_files_gt(1)(s)


def test_plan_has_steps(tmp_path):
    s = _make_state(tmp_path)
    assert not plan_has_steps()(s)
    s["execution_plan"] = {"goal": "g", "steps": [  # type: ignore[typeddict-unknown-key]
        {"id": "s1", "description": "d", "tool_hints": [],
         "files_to_modify": [], "depends_on": [], "status": "pending"}
    ], "risks": []}
    assert plan_has_steps()(s)


def test_validation_passed(tmp_path):
    s = _make_state(tmp_path)
    assert not validation_passed()(s)
    s["validation_results"] = {  # type: ignore[typeddict-unknown-key]
        "passed": True, "pytest_output": "", "mypy_output": "", "ruff_output": "", "errors": []
    }
    assert validation_passed()(s)


# ─── EvalTask ─────────────────────────────────────────────────────────────────

def test_default_tasks_defined():
    assert len(DEFAULT_TASKS) == 5
    ids = {t.id for t in DEFAULT_TASKS}
    assert "fix_bug" in ids
    assert "add_endpoint" in ids
    assert "add_middleware" in ids
    assert "refactor_service" in ids
    assert "improve_tests" in ids


def test_eval_task_fields():
    task = DEFAULT_TASKS[0]
    assert task.objective
    assert task.criteria_labels
    assert len(task.success_criteria) == len(task.criteria_labels)


# ─── TaskMetrics ──────────────────────────────────────────────────────────────

def _make_metrics(success=True, criteria=None, repairs=0, tools=5, elapsed=10.0):
    criteria = criteria or [True, True]
    return TaskMetrics(
        task_id="fix_bug",
        task_name="Fix Bug",
        objective="find and fix bug",
        success=success,
        criteria_results=criteria,
        criteria_labels=["no error", "plan generated"],
        execution_time_s=elapsed,
        tool_call_count=tools,
        repair_attempts=repairs,
        final_phase="pr_generation" if success else "error",
        pr_title="fix: test" if success else None,
        modified_files=["/tmp/test.py"] if success else [],
        error=None if success else "something broke",
    )


def test_task_metrics_completion_rate():
    m = _make_metrics(criteria=[True, False, True])
    assert m.completion_rate == pytest.approx(2 / 3)


def test_task_metrics_to_dict():
    m = _make_metrics()
    d = m.to_dict()
    assert d["task_id"] == "fix_bug"
    assert d["success"] is True
    assert d["completion_rate"] == 1.0
    assert len(d["criteria"]) == 2


# ─── SuiteMetrics ─────────────────────────────────────────────────────────────

def test_suite_success_rate():
    suite = SuiteMetrics(tasks=[
        _make_metrics(success=True),
        _make_metrics(success=False),
        _make_metrics(success=True),
    ])
    assert suite.success_rate == pytest.approx(2 / 3)


def test_suite_averages():
    suite = SuiteMetrics(tasks=[
        _make_metrics(tools=4, elapsed=8.0, repairs=0),
        _make_metrics(tools=6, elapsed=12.0, repairs=2),
    ])
    assert suite.avg_tool_calls == pytest.approx(5.0)
    assert suite.avg_execution_time_s == pytest.approx(10.0)
    assert suite.avg_repair_attempts == pytest.approx(1.0)


def test_suite_to_dict_structure():
    suite = SuiteMetrics(tasks=[_make_metrics(), _make_metrics(success=False)])
    d = suite.to_dict()
    assert "summary" in d
    assert "tasks" in d
    assert d["summary"]["total_tasks"] == 2
    assert 0 < d["summary"]["success_rate"] < 1


def test_suite_empty():
    suite = SuiteMetrics(tasks=[])
    assert suite.success_rate == 0.0
    assert suite.avg_tool_calls == 0.0


# ─── runner (mocked graph) ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_task_success(tmp_path):
    from repopilot.evaluation.runner import _run_task

    task = EvalTask(
        id="test_add",
        name="Test Add",
        objective="add a function",
        success_criteria=[no_error(), plan_has_steps()],
        criteria_labels=["no error", "has plan"],
    )

    def fake_invoke(state):
        state["current_phase"] = "pr_generation"
        state["execution_plan"] = {
            "goal": "g",
            "steps": [{"id": "s1", "description": "d", "tool_hints": [],
                        "files_to_modify": [], "depends_on": [], "status": "done"}],
            "risks": [],
        }
        return state

    with patch("repopilot.graph.workflow.build_graph") as mock_build:
        mock_build.return_value.invoke.side_effect = fake_invoke
        metrics = await _run_task(task, str(tmp_path))

    assert metrics.success is True
    assert metrics.final_phase == "pr_generation"
    assert metrics.criteria_results == [True, True]


@pytest.mark.asyncio
async def test_run_task_failure(tmp_path):
    from repopilot.evaluation.runner import _run_task

    task = EvalTask(
        id="test_fail",
        name="Test Fail",
        objective="do something",
        success_criteria=[no_error()],
        criteria_labels=["no error"],
    )

    with patch("repopilot.graph.workflow.build_graph") as mock_build:
        mock_build.return_value.invoke.side_effect = RuntimeError("graph crashed")
        metrics = await _run_task(task, str(tmp_path))

    assert metrics.success is False
    assert metrics.error is not None
    assert "graph crashed" in metrics.error


@pytest.mark.asyncio
async def test_run_suite_sequential(tmp_path):
    from repopilot.evaluation.runner import run_suite_async

    tasks = [
        EvalTask(id="t1", name="T1", objective="obj1", success_criteria=[no_error()], criteria_labels=["no error"]),
        EvalTask(id="t2", name="T2", objective="obj2", success_criteria=[no_error()], criteria_labels=["no error"]),
    ]

    def fake_invoke(state):
        state["current_phase"] = "pr_generation"
        return state

    with patch("repopilot.graph.workflow.build_graph") as mock_build:
        mock_build.return_value.invoke.side_effect = fake_invoke
        suite = await run_suite_async(tasks, str(tmp_path), parallel=False)

    assert len(suite.tasks) == 2
    assert suite.success_rate == 1.0


# ─── JSON report roundtrip ────────────────────────────────────────────────────

def test_report_json_roundtrip(tmp_path):
    suite = SuiteMetrics(tasks=[_make_metrics(), _make_metrics(success=False, repairs=1)])
    report = suite.to_dict()
    raw = json.dumps(report)
    loaded = json.loads(raw)
    assert loaded["summary"]["total_tasks"] == 2
    assert loaded["tasks"][0]["success"] is True
    assert loaded["tasks"][1]["repair_attempts"] == 1
