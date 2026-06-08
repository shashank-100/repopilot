"""Reflection Agent (Phase 12) — analyses failures and produces a repair plan.

Reads state["validation_results"] and state["execution_plan"], asks the LLM
to identify the root cause, and emits a ReflectionReport containing:
  - failure_summary   — human-readable summary of what broke
  - root_cause        — specific diagnosis
  - plan_patches      — list of ExecutionStep patches for PlanningAgent.replan()
  - retry_strategy    — short description of the new approach

The ReflectionReport is stored in state and the workflow then routes back to
the planning node, which calls PlanningAgent.run() — that detects the
reflection report and incorporates the patches.
"""
from __future__ import annotations

import structlog
from langchain_core.language_models import BaseChatModel

from repopilot.llm import heavy_llm, invoke_with_retry
from pydantic import BaseModel, Field

from repopilot.state import RepoPilotState, ReflectionReport

logger = structlog.get_logger(__name__)


class _ReflectionSchema(BaseModel):
    failure_summary: str = Field(description="What failed and how")
    root_cause: str = Field(description="Specific root cause of the failure")
    plan_patches: list[dict] = Field(
        description=(
            "List of step patches to apply. Each dict must have 'id' (existing step id to update "
            "or a new id), 'description' (updated description), optionally 'files_to_modify', "
            "'tool_hints', 'status' (reset to 'pending' to retry)."
        )
    )
    retry_strategy: str = Field(description="One sentence describing the new approach")


class ReflectionAgent:
    def __init__(self, llm: BaseChatModel | None = None) -> None:
        self._llm = llm or heavy_llm()

    def run(self, state: RepoPilotState) -> RepoPilotState:
        log = logger.bind(run_id=state["run_id"], agent="reflection")
        log.info("agent.start", repair_attempt=state.get("repair_attempts", 0))

        val = state.get("validation_results", {})
        plan = state.get("execution_plan", {})
        failed_steps = [
            s for s in plan.get("steps", []) if s.get("status") == "failed"
        ]

        prompt = (
            f"A code change attempt has failed validation. Analyse the failures and "
            f"produce a concrete repair plan.\n\n"
            f"Objective: {state['objective']}\n"
            f"Repair attempt #{state.get('repair_attempts', 1)} of 3\n\n"
            f"Validation errors:\n"
            + "\n".join(f"  - {e}" for e in val.get("errors", ["(none recorded)"]))
            + f"\n\nPytest output (last 2000 chars):\n{val.get('pytest_output', '')[-2000:]}\n\n"
            f"Mypy output:\n{val.get('mypy_output', '')[-1000:]}\n\n"
            f"Ruff output:\n{val.get('ruff_output', '')[-500:]}\n\n"
            f"Failed plan steps:\n"
            + "\n".join(
                f"  [{s['id']}] {s['description']}" for s in failed_steps
            )
            + f"\n\nAll plan steps:\n"
            + "\n".join(
                f"  [{s['id']}] ({s['status']}) {s['description']}"
                for s in plan.get("steps", [])
            )
            + "\n\nProvide patches to fix the failed steps. "
            "Set status='pending' on any step that should be retried. "
            "Add new steps if the fix requires new work."
        )

        structured_llm = self._llm.with_structured_output(_ReflectionSchema)
        result: _ReflectionSchema = invoke_with_retry(structured_llm, prompt)

        report: ReflectionReport = {
            "failure_summary": result.failure_summary,
            "root_cause": result.root_cause,
            "plan_patches": result.plan_patches,
            "retry_strategy": result.retry_strategy,
        }

        state["reflection_report"] = report
        state["current_phase"] = "reflection"
        state["observations"].append(
            f"reflection: root_cause='{result.root_cause}' | strategy='{result.retry_strategy}'"
        )
        log.info("agent.done", patches=len(result.plan_patches))
        return state
