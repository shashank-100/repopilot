"""Benchmark task definitions for RepoPilot evaluation.

Each EvalTask describes a coding objective to run against a target repository,
plus a set of success criteria that are checked after the run completes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from repopilot.state import RepoPilotState


@dataclass
class EvalTask:
    id: str
    name: str
    objective: str
    # repo_path is injected at run time (can be a fixture or real repo)
    repo_path: str = ""
    # Callables that receive the final RepoPilotState and return True/False
    success_criteria: list[Callable[[RepoPilotState], bool]] = field(default_factory=list)
    # Human-readable descriptions matching each criterion
    criteria_labels: list[str] = field(default_factory=list)
    # Optional: expected phase the run should reach
    expected_phase: str = "pr_generation"


# ── built-in criterion helpers ────────────────────────────────────────────────

def reached_phase(phase: str) -> Callable[[RepoPilotState], bool]:
    return lambda s: s.get("current_phase") == phase


def has_pr() -> Callable[[RepoPilotState], bool]:
    return lambda s: bool(s.get("generated_pr"))


def modified_files_gt(n: int) -> Callable[[RepoPilotState], bool]:
    return lambda s: len(s.get("modified_files", [])) > n


def validation_passed() -> Callable[[RepoPilotState], bool]:
    val = lambda s: (s.get("validation_results") or {}).get("passed", False)
    return val


def plan_has_steps() -> Callable[[RepoPilotState], bool]:
    return lambda s: len((s.get("execution_plan") or {}).get("steps", [])) > 0


def no_error() -> Callable[[RepoPilotState], bool]:
    return lambda s: s.get("current_phase") != "error"


# ── default benchmark suite ───────────────────────────────────────────────────

DEFAULT_TASKS: list[EvalTask] = [
    EvalTask(
        id="fix_bug",
        name="Fix Bug",
        objective="Find and fix the first failing test in the repository",
        success_criteria=[no_error(), plan_has_steps(), reached_phase("pr_generation")],
        criteria_labels=["no error", "plan generated", "reached PR generation"],
    ),
    EvalTask(
        id="add_endpoint",
        name="Add Endpoint",
        objective="Add a GET /ping endpoint that returns {\"pong\": true}",
        success_criteria=[no_error(), plan_has_steps(), modified_files_gt(0), has_pr()],
        criteria_labels=["no error", "plan generated", "files modified", "PR generated"],
    ),
    EvalTask(
        id="add_middleware",
        name="Add Middleware",
        objective="Add rate limiting middleware to all API routes using slowapi or similar",
        success_criteria=[no_error(), plan_has_steps(), modified_files_gt(0)],
        criteria_labels=["no error", "plan generated", "files modified"],
    ),
    EvalTask(
        id="refactor_service",
        name="Refactor Service",
        objective="Extract repeated database query logic into a reusable helper function",
        success_criteria=[no_error(), plan_has_steps()],
        criteria_labels=["no error", "plan generated"],
    ),
    EvalTask(
        id="improve_tests",
        name="Improve Tests",
        objective="Add parametrised pytest tests for all existing utility functions",
        success_criteria=[no_error(), plan_has_steps(), modified_files_gt(0)],
        criteria_labels=["no error", "plan generated", "test files modified"],
    ),
]
