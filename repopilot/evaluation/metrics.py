"""Metrics computed from a completed evaluation run."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TaskMetrics:
    task_id: str
    task_name: str
    objective: str
    # Outcome
    success: bool           # all criteria passed
    criteria_results: list[bool]
    criteria_labels: list[str]
    # Timing
    execution_time_s: float
    # Agent behaviour
    tool_call_count: int
    repair_attempts: int
    final_phase: str
    # Optional artefacts
    pr_title: str | None
    modified_files: list[str]
    error: str | None

    @property
    def completion_rate(self) -> float:
        """Fraction of criteria that passed."""
        if not self.criteria_results:
            return 0.0
        return sum(self.criteria_results) / len(self.criteria_results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "objective": self.objective,
            "success": self.success,
            "completion_rate": round(self.completion_rate, 3),
            "criteria": [
                {"label": lbl, "passed": res}
                for lbl, res in zip(self.criteria_labels, self.criteria_results)
            ],
            "execution_time_s": round(self.execution_time_s, 2),
            "tool_call_count": self.tool_call_count,
            "repair_attempts": self.repair_attempts,
            "final_phase": self.final_phase,
            "pr_title": self.pr_title,
            "modified_files": self.modified_files,
            "error": self.error,
        }


@dataclass
class SuiteMetrics:
    tasks: list[TaskMetrics]

    @property
    def success_rate(self) -> float:
        if not self.tasks:
            return 0.0
        return sum(t.success for t in self.tasks) / len(self.tasks)

    @property
    def avg_completion_rate(self) -> float:
        if not self.tasks:
            return 0.0
        return sum(t.completion_rate for t in self.tasks) / len(self.tasks)

    @property
    def avg_execution_time_s(self) -> float:
        if not self.tasks:
            return 0.0
        return sum(t.execution_time_s for t in self.tasks) / len(self.tasks)

    @property
    def avg_tool_calls(self) -> float:
        if not self.tasks:
            return 0.0
        return sum(t.tool_call_count for t in self.tasks) / len(self.tasks)

    @property
    def avg_repair_attempts(self) -> float:
        if not self.tasks:
            return 0.0
        return sum(t.repair_attempts for t in self.tasks) / len(self.tasks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "total_tasks": len(self.tasks),
                "success_rate": round(self.success_rate, 3),
                "avg_completion_rate": round(self.avg_completion_rate, 3),
                "avg_execution_time_s": round(self.avg_execution_time_s, 2),
                "avg_tool_calls": round(self.avg_tool_calls, 1),
                "avg_repair_attempts": round(self.avg_repair_attempts, 2),
            },
            "tasks": [t.to_dict() for t in self.tasks],
        }
