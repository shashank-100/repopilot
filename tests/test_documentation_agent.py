"""Tests for Phase 13: DocumentationAgent."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repopilot.agents.documentation import DocumentationAgent, _DocResult
from repopilot.state_store import create_run, delete_run
from repopilot.tools.base import ToolOutput, load_all_tools, registry
from repopilot.tools.executor import ToolExecutor


def _make_state(tmp_path: Path, modified: list[str] | None = None):
    state = create_run("add caching", str(tmp_path))
    state["modified_files"] = modified or []
    state["execution_plan"] = {"goal": "add caching", "steps": [], "risks": []}
    return state


def _real_executor(state):
    load_all_tools()
    return ToolExecutor(registry, state)


def _fake_doc_result(updated: str) -> _DocResult:
    return _DocResult(
        module_docstring="Updated module docstring.",
        migration_note="Added caching support.",
        updated_content=updated,
    )


def test_no_modified_files_skips(tmp_path):
    state = _make_state(tmp_path, modified=[])
    agent = DocumentationAgent(executor=_real_executor(state))
    result = agent.run(state)
    assert result["current_phase"] == "documentation"
    assert any("no modified files" in obs for obs in result["observations"])
    delete_run(state["run_id"])


def test_non_python_files_skipped(tmp_path):
    f = tmp_path / "README.md"
    f.write_text("# hello")
    state = _make_state(tmp_path, modified=[str(f)])
    agent = DocumentationAgent(executor=_real_executor(state))
    with patch.object(DocumentationAgent, "_generate_docs") as mock_gen:
        result = agent.run(state)
    mock_gen.assert_not_called()
    delete_run(state["run_id"])


def test_python_file_gets_updated(tmp_path):
    f = tmp_path / "cache.py"
    f.write_text("def get(key): pass\n")
    state = _make_state(tmp_path, modified=[str(f)])
    executor = _real_executor(state)

    updated = '"""Cache module — provides get/set helpers."""\ndef get(key): pass\n'
    with patch.object(DocumentationAgent, "_generate_docs", return_value=_fake_doc_result(updated)):
        agent = DocumentationAgent(executor=executor)
        result = agent.run(state)

    assert f.read_text() == updated
    assert any("1 file" in obs for obs in result["observations"])
    delete_run(state["run_id"])


def test_migration_notes_stored_in_plan(tmp_path):
    f = tmp_path / "service.py"
    f.write_text("class Service: pass\n")
    state = _make_state(tmp_path, modified=[str(f)])
    executor = _real_executor(state)

    with patch.object(DocumentationAgent, "_generate_docs",
                      return_value=_fake_doc_result("class Service: pass\n")):
        agent = DocumentationAgent(executor=executor)
        result = agent.run(state)

    notes = result["execution_plan"].get("migration_notes", [])
    assert len(notes) == 1
    assert "service.py" in notes[0]
    delete_run(state["run_id"])


def test_llm_error_does_not_crash(tmp_path):
    f = tmp_path / "broken.py"
    f.write_text("x = 1\n")
    state = _make_state(tmp_path, modified=[str(f)])
    executor = _real_executor(state)

    with patch.object(DocumentationAgent, "_generate_docs", side_effect=RuntimeError("llm down")):
        agent = DocumentationAgent(executor=executor)
        result = agent.run(state)  # should not raise

    assert result["current_phase"] == "documentation"
    delete_run(state["run_id"])


def test_no_stubs_in_workflow():
    from repopilot.graph.workflow import build_graph
    g = build_graph(phases=["documentation"])
    assert "documentation" in list(g.get_graph().nodes)
