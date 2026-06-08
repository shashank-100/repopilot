"""Tests for the advisory, tiered ValidationAgent."""
from __future__ import annotations

from unittest.mock import MagicMock

from repopilot.agents.validation import (
    ValidationAgent,
    _has_npm_test,
    _has_python_tests,
    _syntax_check,
)
from repopilot.state_store import create_run, delete_run
from repopilot.tools.base import ToolOutput


def _mock_executor(pytest_rc=0, pytest_ok=True):
    ex = MagicMock()

    def run(tool_name, **kwargs):
        if tool_name == "terminal.run_pytest":
            return ToolOutput(success=pytest_ok, data={"returncode": pytest_rc, "stdout": "out", "stderr": ""})
        if tool_name == "terminal.run_command":
            return ToolOutput(success=pytest_ok, data={"returncode": pytest_rc, "stdout": "out", "stderr": ""})
        return ToolOutput(success=True, data={})

    ex.run.side_effect = run
    return ex


# ── tier detection ──────────────────────────────────────────────────────────

def test_has_python_tests(tmp_path):
    assert not _has_python_tests(str(tmp_path))
    (tmp_path / "test_foo.py").write_text("def test_x(): pass")
    assert _has_python_tests(str(tmp_path))


def test_has_npm_test(tmp_path):
    assert not _has_npm_test(str(tmp_path))
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}')
    assert _has_npm_test(str(tmp_path))
    # default placeholder is not a real test
    (tmp_path / "package.json").write_text('{"scripts": {"test": "echo no test specified"}}')
    assert not _has_npm_test(str(tmp_path))


# ── syntax check ────────────────────────────────────────────────────────────

def test_syntax_check_python(tmp_path):
    good = tmp_path / "ok.py"; good.write_text("x = 1\n")
    bad = tmp_path / "bad.py"; bad.write_text("def f(:\n")
    findings = _syntax_check([str(good), str(bad)])
    assert len(findings) == 1
    assert "bad.py" in findings[0]


def test_syntax_check_json(tmp_path):
    bad = tmp_path / "x.json"; bad.write_text("{not valid}")
    findings = _syntax_check([str(bad)])
    assert any("invalid JSON" in f for f in findings)


# ── advisory behaviour ──────────────────────────────────────────────────────

def test_tests_pass(tmp_path):
    (tmp_path / "test_a.py").write_text("def test_x(): pass")
    state = create_run("t", str(tmp_path))
    state["modified_files"] = [str(tmp_path / "test_a.py")]
    result = ValidationAgent(executor=_mock_executor(pytest_rc=0)).run(state)
    v = result["validation_results"]
    assert v["validated_with"] == "tests"
    assert v["severity"] == "pass"
    assert v["passed"] is True
    delete_run(state["run_id"])


def test_tests_fail_is_warning_not_block(tmp_path):
    (tmp_path / "test_a.py").write_text("def test_x(): assert False")
    state = create_run("t", str(tmp_path))
    result = ValidationAgent(executor=_mock_executor(pytest_rc=1, pytest_ok=False)).run(state)
    v = result["validation_results"]
    assert v["severity"] == "warnings"
    assert v["passed"] is False
    # advisory: phase still advances
    assert result["current_phase"] == "validation"
    delete_run(state["run_id"])


def test_no_tests_no_config_is_not_validated(tmp_path):
    # plain repo, no tests, no lint config, no modified files
    state = create_run("t", str(tmp_path))
    result = ValidationAgent(executor=_mock_executor()).run(state)
    v = result["validation_results"]
    assert v["severity"] == "not_validated"
    assert v["validated_with"] == "none"
    delete_run(state["run_id"])


def test_syntax_tier_when_only_changed_files(tmp_path):
    # no tests/lint, but a changed file that parses cleanly → pass via syntax
    f = tmp_path / "mod.py"; f.write_text("x = 1\n")
    state = create_run("t", str(tmp_path))
    state["modified_files"] = [str(f)]
    result = ValidationAgent(executor=_mock_executor()).run(state)
    v = result["validation_results"]
    assert v["validated_with"] == "syntax"
    assert v["severity"] == "pass"
    delete_run(state["run_id"])


def test_syntax_error_is_warning(tmp_path):
    f = tmp_path / "broken.py"; f.write_text("def f(:\n")
    state = create_run("t", str(tmp_path))
    state["modified_files"] = [str(f)]
    result = ValidationAgent(executor=_mock_executor()).run(state)
    v = result["validation_results"]
    assert v["validated_with"] == "syntax"
    assert v["severity"] == "warnings"
    assert any("broken.py" in x for x in v["findings"])
    delete_run(state["run_id"])


# ── routing ──────────────────────────────────────────────────────────────────

def test_route_advisory_never_blocks_on_not_validated():
    from repopilot.graph.workflow import _route_after_validation
    state = {"validation_results": {"severity": "not_validated", "validated_with": "none"}, "repair_attempts": 0}
    assert _route_after_validation(state) == "pass"  # type: ignore[arg-type]


def test_route_repairs_on_test_failure():
    from repopilot.graph.workflow import _route_after_validation
    state = {"validation_results": {"severity": "warnings", "validated_with": "tests"}, "repair_attempts": 0}
    assert _route_after_validation(state) == "repair"  # type: ignore[arg-type]


def test_route_passes_on_syntax_warning():
    from repopilot.graph.workflow import _route_after_validation
    state = {"validation_results": {"severity": "warnings", "validated_with": "syntax"}, "repair_attempts": 0}
    assert _route_after_validation(state) == "pass"  # type: ignore[arg-type]


def test_route_passes_after_max_repairs():
    from repopilot.graph.workflow import _route_after_validation
    state = {"validation_results": {"severity": "warnings", "validated_with": "tests"}, "repair_attempts": 3}
    assert _route_after_validation(state) == "pass"  # type: ignore[arg-type]


def test_no_stubs_in_workflow():
    from repopilot.graph.workflow import build_graph
    g = build_graph(phases=["validation"])
    assert "validation" in list(g.get_graph().nodes)
