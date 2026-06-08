"""Implementation Agent — executes execution_plan steps to modify the repository.

For each pending step the agent:
1. Reads relevant files identified in the step's `files_to_modify` list.
2. Calls the LLM with the full step context to produce concrete file edits.
3. Applies edits via fs.write_file (or fs.read_file + patch).
4. Marks the step done and records changed paths in state["modified_files"].

On any step failure the step is marked "failed", an observation is appended,
and execution continues with the remaining steps so downstream validation can
report exactly what broke.
"""
from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel

import json

from repopilot.llm import default_llm, invoke_with_retry
from pydantic import BaseModel, Field, field_validator

from repopilot.state import RepoPilotState
from repopilot.tools.base import load_all_tools, registry
from repopilot.tools.executor import ToolExecutor

logger = structlog.get_logger(__name__)

# Maximum characters of existing file content sent to the LLM per step.
_MAX_FILE_CONTEXT = 6000


class _FileEdit(BaseModel):
    path: str = Field(description="Absolute or repo-relative file path to write")
    content: str = Field(description="Complete new file content (not a diff)")
    is_new: bool = Field(default=False, description="True if this file does not exist yet")


class _StepResult(BaseModel):
    summary: str = Field(description="One sentence describing what was done")
    edits: list[_FileEdit] = Field(description="Files to create or overwrite")
    observations: list[str] = Field(default_factory=list, description="Noteworthy findings")

    @field_validator("edits", mode="before")
    @classmethod
    def _coerce_edits(cls, v: object) -> object:
        """Haiku sometimes returns `edits` as a JSON STRING instead of a list.

        Parse it back into a list so the step's file edits aren't silently
        dropped (see the CrowdDJ run where step 9 lost base.js). Pydantic then
        validates the parsed items against _FileEdit as normal.
        """
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict):
                    return [parsed]
            except (json.JSONDecodeError, ValueError):
                return []  # unparseable → no edits, but don't crash the step
        return v

    @field_validator("observations", mode="before")
    @classmethod
    def _coerce_obs(cls, v: object) -> object:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except (json.JSONDecodeError, ValueError):
                return [v]
        return v


class ImplementationAgent:
    def __init__(
        self,
        llm: BaseChatModel | None = None,
        executor: ToolExecutor | None = None,
    ) -> None:
        self._llm = llm or default_llm()
        self._executor = executor
        # Per-run cache: abs_path -> file content.
        # Avoids re-reading + re-embedding the same file on every step.
        self._file_cache: dict[str, str] = {}
        # Paths whose full content has already been shown to the LLM this run.
        self._shown: set[str] = set()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, state: RepoPilotState) -> RepoPilotState:
        log = logger.bind(run_id=state["run_id"], agent="implementation")
        log.info("agent.start")

        plan = state.get("execution_plan")
        if not plan or not plan.get("steps"):
            state["observations"].append("implementation: no execution_plan — skipped")
            state["current_phase"] = "implementation"
            log.warning("agent.no_plan")
            return state

        executor = self._executor or self._make_executor(state)
        steps: list[dict[str, Any]] = plan["steps"]
        completed = 0
        # Fresh cache for each run
        self._file_cache = {}
        self._shown = set()

        for step in steps:
            if step.get("status") in ("done", "failed"):
                continue

            step_log = log.bind(step_id=step["id"])
            step_log.info("step.start", description=step["description"])

            try:
                result = self._execute_step(step, state, executor)
                self._apply_edits(result.edits, state, executor, step_log)
                step["status"] = "done"
                completed += 1
                state["observations"].append(f"step {step['id']}: {result.summary}")
                for obs in result.observations:
                    state["observations"].append(f"  → {obs}")
                step_log.info("step.done")
            except Exception as exc:
                step["status"] = "failed"
                msg = f"step {step['id']} failed: {exc}"
                state["observations"].append(msg)
                step_log.warning("step.failed", error=str(exc))

        plan["steps"] = steps
        state["execution_plan"] = plan
        state["current_phase"] = "implementation"
        log.info("agent.done", completed=completed, total=len(steps))
        return state

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_executor(self, state: RepoPilotState) -> ToolExecutor:
        load_all_tools()
        return ToolExecutor(registry, state)

    def _get_file(self, abs_path: str, executor: ToolExecutor) -> str | None:
        """Return file content, reading from disk only on a cache miss."""
        if abs_path in self._file_cache:
            return self._file_cache[abs_path]
        result = executor.run("fs.read_file", path=abs_path)
        if result.success:
            content: str = result.data.get("content", "")
            self._file_cache[abs_path] = content
            return content
        return None

    def _read_existing_files(
        self,
        files: list[str],
        repo_path: str,
        executor: ToolExecutor,
    ) -> str:
        """Return file context for the LLM.

        Each file's full content is embedded only ONCE per run. On later steps
        the same file is referenced by name only ("already shown above") unless
        it was modified by a write since (which clears it from `_shown`).
        """
        parts: list[str] = []
        budget = _MAX_FILE_CONTEXT

        for rel_path in files:
            abs_path = rel_path if rel_path.startswith("/") else f"{repo_path}/{rel_path}"
            content = self._get_file(abs_path, executor)

            if content is None:
                parts.append(f"### {rel_path}\n(file not found — will be created)")
                continue

            if abs_path in self._shown:
                # Already embedded in an earlier step's prompt — don't resend.
                parts.append(f"### {rel_path}\n(unchanged — full content shown earlier)")
                continue

            if budget <= 0:
                parts.append(f"### {rel_path}\n(omitted — context budget reached)")
                continue

            snippet = content[:budget]
            parts.append(f"### {rel_path}\n```\n{snippet}\n```")
            budget -= len(snippet)
            self._shown.add(abs_path)

        return "\n\n".join(parts)

    def _execute_step(
        self,
        step: dict[str, Any],
        state: RepoPilotState,
        executor: ToolExecutor,
    ) -> _StepResult:
        repo_path = state["repo_path"]
        files_to_modify: list[str] = step.get("files_to_modify", [])
        existing = self._read_existing_files(files_to_modify, repo_path, executor)

        repo_map = state.get("repository_map", {})
        arch = state.get("architecture_context", {})

        prompt = (
            f"You are implementing ONE step of a code change.\n\n"
            f"Objective: {state['objective']}\n"
            f"Repository path: {repo_path}\n"
            f"Framework: {repo_map.get('framework', 'unknown')}\n"
            f"Architecture summary: {arch.get('summary', 'N/A')}\n\n"
            f"Current step ({step['id']}): {step['description']}\n"
            f"Tool hints: {', '.join(step.get('tool_hints', []))}\n\n"
        )
        if existing:
            prompt += f"Existing file contents:\n{existing}\n\n"
        prompt += (
            "STRICT RULES:\n"
            "1. Make the MINIMAL change required by THIS step and the objective only.\n"
            "2. Do NOT refactor, rename, reformat, or 'improve' code that the step "
            "does not explicitly require.\n"
            "3. Do NOT change existing function bodies, return values, test "
            "assertions, or messages unless the step explicitly says to.\n"
            "4. Preserve all existing behavior, imports, and style not related to the change.\n"
            "5. Only edit the files this step needs. Do not create extra helper/config "
            "files unless the step requires them.\n\n"
            "Return the COMPLETE new content for each file you change "
            "(full file, not a diff), using absolute paths prefixed with the repository path."
        )

        structured_llm = self._llm.with_structured_output(_StepResult)
        result: _StepResult = invoke_with_retry(structured_llm, prompt)
        return result

    def _apply_edits(
        self,
        edits: list[_FileEdit],
        state: RepoPilotState,
        executor: ToolExecutor,
        log: Any,
    ) -> None:
        for edit in edits:
            path = edit.path
            # Normalise to absolute path
            if not path.startswith("/"):
                path = f"{state['repo_path']}/{path}"

            result = executor.run("fs.write_file", path=path, content=edit.content)
            if result.success:
                if path not in state["modified_files"]:
                    state["modified_files"].append(path)
                # Update cache with the new content and force a re-show next
                # time this file appears, since it has changed.
                self._file_cache[path] = edit.content
                self._shown.discard(path)
                log.info("edit.applied", path=path, is_new=edit.is_new)
            else:
                raise RuntimeError(f"fs.write_file failed for {path}: {result.error}")
