"""Tests for Phase 15 resilience: typed errors + retry/backoff on LLM calls."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from anthropic import APIConnectionError

from repopilot.errors import (
    AgentError,
    LLMError,
    PersistenceError,
    RepoPilotError,
    StateError,
    ToolError,
    ToolNotFoundError,
)
from repopilot.llm import invoke_with_retry


# ── typed error hierarchy ──────────────────────────────────────────────────────

def test_error_hierarchy():
    assert issubclass(ToolError, RepoPilotError)
    assert issubclass(LLMError, RepoPilotError)
    assert issubclass(AgentError, RepoPilotError)
    assert issubclass(PersistenceError, StateError)
    assert issubclass(StateError, RepoPilotError)


def test_tool_error_message():
    e = ToolError("fs.read_file", "file not found")
    assert e.tool_name == "fs.read_file"
    assert "fs.read_file" in str(e)


def test_agent_error_message():
    e = AgentError("planning", "no plan produced")
    assert e.agent == "planning"
    assert "planning" in str(e)


def test_tool_not_found_raised_by_executor():
    from repopilot.tools.base import load_all_tools, registry
    from repopilot.tools.executor import ToolExecutor
    from repopilot.state_store import create_run, delete_run

    load_all_tools()
    state = create_run("t", "/tmp")
    ex = ToolExecutor(registry, state)
    with pytest.raises(ToolNotFoundError):
        ex.run("nonexistent.tool")
    delete_run(state["run_id"])


# ── retry / backoff ─────────────────────────────────────────────────────────────

def test_invoke_with_retry_success():
    runnable = MagicMock()
    runnable.invoke.return_value = "ok"
    assert invoke_with_retry(runnable, "prompt") == "ok"
    runnable.invoke.assert_called_once()


def test_invoke_with_retry_retries_transient():
    runnable = MagicMock()
    # Fail twice with a transient error, then succeed
    err = APIConnectionError(request=MagicMock())
    runnable.invoke.side_effect = [err, err, "recovered"]
    result = invoke_with_retry(runnable, "prompt")
    assert result == "recovered"
    assert runnable.invoke.call_count == 3


def test_invoke_with_retry_wraps_nontransient():
    runnable = MagicMock()
    runnable.invoke.side_effect = ValueError("bad schema")
    with pytest.raises(LLMError):
        invoke_with_retry(runnable, "prompt")
    # Non-transient → no retry, single attempt
    runnable.invoke.assert_called_once()
