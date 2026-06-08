"""Typed exception hierarchy for RepoPilot.

All internal failures derive from RepoPilotError so callers can catch the
whole family or narrow to a specific failure mode. Tools convert these into
ToolOutput(success=False, error=...) at the boundary, but the typed classes
make intent explicit and let observability tag failures by category.
"""
from __future__ import annotations


class RepoPilotError(Exception):
    """Base class for all RepoPilot errors."""


class ToolError(RepoPilotError):
    """A tool failed to execute (filesystem, git, terminal, etc.)."""

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"[{tool_name}] {message}")


class ToolNotFoundError(RepoPilotError):
    """Requested tool is not registered."""


class AgentError(RepoPilotError):
    """An agent failed during its run."""

    def __init__(self, agent: str, message: str) -> None:
        self.agent = agent
        super().__init__(f"[{agent}] {message}")


class ValidationError(RepoPilotError):
    """Validation (pytest/mypy/ruff) found problems."""


class LLMError(RepoPilotError):
    """An LLM call failed after exhausting retries."""


class StateError(RepoPilotError):
    """Run state could not be read or written."""


class PersistenceError(StateError):
    """Database-backed state operation failed."""
