"""Planning Agent — generates a structured execution plan for the objective."""
from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel

from repopilot.llm import heavy_llm, invoke_with_retry
from pydantic import BaseModel, Field

from repopilot.state import RepoPilotState

logger = structlog.get_logger(__name__)


class _Step(BaseModel):
    id: str
    description: str
    tool_hints: list[str] = Field(description="Suggested tool names like 'fs.write_file'")
    files_to_modify: list[str] = []
    depends_on: list[str] = []
    status: str = "pending"


class _PlanSchema(BaseModel):
    goal: str = Field(description="Clear restatement of the objective")
    steps: list[_Step] = Field(description="Ordered list of implementation steps")
    risks: list[str] = Field(default_factory=list, description="Potential risks or gotchas")


class PlanningAgent:
    def __init__(self, llm: BaseChatModel | None = None) -> None:
        self._llm = llm or heavy_llm()

    def run(self, state: RepoPilotState) -> RepoPilotState:
        log = logger.bind(run_id=state["run_id"], agent="planning")
        log.info("agent.start")

        arch = state.get("architecture_context", {})
        repo_map = state.get("repository_map", {})
        reflection = state.get("reflection_report")

        replan_context = ""
        if reflection:
            replan_context = (
                f"\n\nPrevious plan failed. Reflection report:\n"
                f"Root cause: {reflection.get('root_cause', '')}\n"
                f"Retry strategy: {reflection.get('retry_strategy', '')}\n"
                f"Apply these patches: {reflection.get('plan_patches', [])}"
            )

        structured_llm = self._llm.with_structured_output(_PlanSchema)
        result: _PlanSchema = invoke_with_retry(
            structured_llm,
            f"Create a step-by-step implementation plan for this objective.\n\n"
            f"Objective: {state['objective']}\n\n"
            f"Repository summary: {repo_map.get('summary', 'N/A')}\n"
            f"Framework: {repo_map.get('framework', 'N/A')}\n"
            f"Architecture summary: {arch.get('summary', 'N/A')}\n"
            f"API routes: {arch.get('api_routes', [])[:10]}\n"
            f"Data models: {arch.get('data_models', [])[:10]}"
            f"{replan_context}\n\n"
            "RULES:\n"
            "- Keep the plan MINIMAL — only steps the objective directly requires.\n"
            "- Do NOT add steps that install dependencies, force-reinstall packages, "
            "or create self-healing pip/conftest hooks. Assume the environment is set up.\n"
            "- Do NOT add steps that 'verify across every interpreter' or run shell "
            "loops — keep at most one validation step.\n"
            "- Prefer 3-6 focused steps over many defensive ones.\n\n"
            f"Available tools: fs.read_file, fs.write_file, fs.find_files, fs.grep_files, "
            f"git.git_diff, git.commit_changes, terminal.run_pytest, terminal.run_mypy, "
            f"analysis.find_routes, analysis.find_models, subagent.spawn_subgraph"
        )

        state["execution_plan"] = {
            "goal": result.goal,
            "steps": [s.model_dump() for s in result.steps],
            "risks": result.risks,
        }
        state["current_phase"] = "planning"
        state["observations"].append(f"Plan created: {len(result.steps)} steps for '{result.goal}'")
        log.info("agent.done", step_count=len(result.steps))
        return state

    def replan(self, state: RepoPilotState, patches: list[dict[str, Any]]) -> RepoPilotState:
        """Apply patches to existing plan steps without full re-plan."""
        plan = state.get("execution_plan", {})
        steps: list[dict[str, Any]] = plan.get("steps", [])
        step_index = {s["id"]: i for i, s in enumerate(steps)}

        for patch in patches:
            step_id = patch.get("id")
            if step_id and step_id in step_index:
                steps[step_index[step_id]].update(patch)
            else:
                # New step
                steps.append({**patch, "status": "pending"})

        plan["steps"] = steps
        state["execution_plan"] = plan
        return state
