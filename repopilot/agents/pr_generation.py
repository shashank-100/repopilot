"""PR Generation Agent (Phase 14) — produces a production-ready PR summary.

Reads the full run context (objective, modified files, validation results,
migration notes, execution plan) and generates a GeneratedPR stored in
state["generated_pr"].

Output shape (matches state.GeneratedPR):
  title          — short imperative PR title
  summary        — paragraph describing what was done and why
  changes        — bullet list of concrete changes
  tests_executed — list of test suites / commands that were run
  risks          — potential risks or edge cases
  rollback_plan  — how to revert if something goes wrong
"""
from __future__ import annotations

from pathlib import Path

import structlog
from langchain_core.language_models import BaseChatModel

from repopilot.llm import heavy_llm, invoke_with_retry
from pydantic import BaseModel, Field, field_validator

from repopilot.state import GeneratedPR, RepoPilotState

logger = structlog.get_logger(__name__)


def _coerce_list(v: object) -> list[str]:
    """Coerce a markdown bullet string into a list (Haiku sometimes returns strings)."""
    if isinstance(v, list):
        return [str(x) for x in v]
    if isinstance(v, str):
        items = []
        for line in v.splitlines():
            line = line.strip().lstrip("-*•").strip().strip('"')
            if line:
                items.append(line)
        return items or [v.strip()]
    return []


class _PRSchema(BaseModel):
    title: str = Field(description="Short imperative PR title (≤72 chars)")
    summary: str = Field(description="1-3 paragraph description of what was done and why")
    changes: list[str] = Field(description="Bullet list of concrete changes made")
    tests_executed: list[str] = Field(description="Test commands / suites that were run")
    risks: list[str] = Field(description="Potential risks, edge cases, or things to watch")
    rollback_plan: str = Field(description="How to revert these changes safely")

    @field_validator("changes", "tests_executed", "risks", mode="before")
    @classmethod
    def _ensure_list(cls, v: object) -> list[str]:
        return _coerce_list(v)


class PRAgent:
    def __init__(self, llm: BaseChatModel | None = None) -> None:
        self._llm = llm or heavy_llm()

    def run(self, state: RepoPilotState) -> RepoPilotState:
        log = logger.bind(run_id=state["run_id"], agent="pr_generation")
        log.info("agent.start")

        val = state.get("validation_results", {})
        plan = state.get("execution_plan", {})
        repo_map = state.get("repository_map", {})
        modified = state.get("modified_files", [])
        migration_notes: list[str] = plan.get("migration_notes", [])

        steps_done = [
            s for s in plan.get("steps", []) if s.get("status") == "done"
        ]
        steps_failed = [
            s for s in plan.get("steps", []) if s.get("status") == "failed"
        ]

        # Honestly describe how the change was validated (advisory tiers).
        validated_with = val.get("validated_with", "none")
        tests_run: list[str] = []
        if validated_with == "tests":
            tests_run.append("Ran the repository test suite")
        elif validated_with == "lint":
            tests_run.append("Static analysis (lint / type check)")
        elif validated_with == "syntax":
            tests_run.append("Syntax check of changed files")
        else:
            tests_run.append("No automated tests available for this repo — change is unverified")

        changed_file_names = [Path(p).name for p in modified]

        prompt = (
            f"Generate a production-ready pull request description for this code change.\n\n"
            f"Objective: {state['objective']}\n"
            f"Repository: {repo_map.get('framework', 'unknown')} — {repo_map.get('summary', '')}\n\n"
            f"Modified files ({len(modified)}):\n"
            + "\n".join(f"  - {p}" for p in modified)
            + f"\n\nCompleted steps ({len(steps_done)}):\n"
            + "\n".join(f"  - {s['description']}" for s in steps_done)
            + (
                f"\n\nFailed steps ({len(steps_failed)}):\n"
                + "\n".join(f"  - {s['description']}" for s in steps_failed)
                if steps_failed else ""
            )
            + f"\n\nMigration notes:\n"
            + "\n".join(f"  - {n}" for n in migration_notes)
            + f"\n\nValidation ({validated_with}): {val.get('summary', 'n/a')}\n"
            + (("Findings:\n" + "\n".join(f"  - {x}" for x in val.get('findings', []))) if val.get('findings') else "")
            + f"\nRepair attempts: {state.get('repair_attempts', 0)}\n\n"
            "Write a complete, honest PR description. "
            "If steps failed, note that in risks. "
            "The rollback_plan should reference the specific files changed."
        )

        structured_llm = self._llm.with_structured_output(_PRSchema)
        result: _PRSchema = invoke_with_retry(structured_llm, prompt)

        pr: GeneratedPR = {
            "title": result.title,
            "summary": result.summary,
            "changes": result.changes,
            "tests_executed": tests_run or result.tests_executed,
            "risks": result.risks,
            "rollback_plan": result.rollback_plan,
        }

        state["generated_pr"] = pr
        state["current_phase"] = "pr_generation"
        state["observations"].append(f"pr_generation: '{result.title}'")
        log.info("agent.done", title=result.title)
        return state
