"""Documentation Agent (Phase 13) — updates docs for every modified file.

For each file in state["modified_files"] the agent:
  1. Reads the current file content.
  2. Asks the LLM (Haiku — cheap) to produce:
       - An updated module-level docstring.
       - A short migration note (what changed and why).
  3. Writes the docstring back into the file if it changed.
  4. Appends migration notes to state["observations"] and collects them
     for the PR agent.

Migration notes are stored under state["execution_plan"]["migration_notes"]
so the PR agent can include them verbatim.
"""
from __future__ import annotations

from pathlib import Path

import structlog
from langchain_core.language_models import BaseChatModel

from repopilot.llm import default_llm, invoke_with_retry
from pydantic import BaseModel, Field

from repopilot.state import RepoPilotState
from repopilot.tools.base import load_all_tools, registry
from repopilot.tools.executor import ToolExecutor

logger = structlog.get_logger(__name__)

_MAX_FILE_CHARS = 5000


class _DocResult(BaseModel):
    module_docstring: str = Field(
        description="Updated module-level docstring (triple-quoted string body only, no quotes)"
    )
    migration_note: str = Field(
        description="One or two sentences describing what changed in this file and why"
    )
    updated_content: str = Field(
        description="Complete updated file content with the new module docstring inserted/replaced"
    )


class DocumentationAgent:
    def __init__(
        self,
        llm: BaseChatModel | None = None,
        executor: ToolExecutor | None = None,
    ) -> None:
        self._llm = llm or default_llm()
        self._executor = executor

    def run(self, state: RepoPilotState) -> RepoPilotState:
        log = logger.bind(run_id=state["run_id"], agent="documentation")
        log.info("agent.start")

        modified: list[str] = state.get("modified_files", [])
        if not modified:
            state["observations"].append("documentation: no modified files — skipped")
            state["current_phase"] = "documentation"
            log.info("agent.skip", reason="no modified files")
            return state

        executor = self._executor or self._make_executor(state)
        migration_notes: list[str] = []

        for path in modified:
            if not path.endswith(".py"):
                continue
            abs_path = path if path.startswith("/") else f"{state['repo_path']}/{path}"
            read_res = executor.run("fs.read_file", path=abs_path)
            if not read_res.success:
                log.warning("doc.skip_unreadable", path=abs_path)
                continue

            content: str = read_res.data.get("content", "")
            if not content.strip():
                continue

            try:
                doc_result = self._generate_docs(content[:_MAX_FILE_CHARS], abs_path, state)
            except Exception as exc:
                log.warning("doc.llm_error", path=abs_path, error=str(exc))
                continue

            write_res = executor.run(
                "fs.write_file", path=abs_path, content=doc_result.updated_content
            )
            if write_res.success:
                log.info("doc.updated", path=abs_path)
                migration_notes.append(f"{Path(abs_path).name}: {doc_result.migration_note}")
            else:
                log.warning("doc.write_failed", path=abs_path, error=write_res.error)

        # Store migration notes for the PR agent
        plan = state.get("execution_plan", {})
        plan["migration_notes"] = migration_notes
        state["execution_plan"] = plan

        state["current_phase"] = "documentation"
        state["observations"].append(
            f"documentation: updated {len(migration_notes)} file(s)"
        )
        log.info("agent.done", updated=len(migration_notes))
        return state

    # ------------------------------------------------------------------

    def _generate_docs(
        self, content: str, path: str, state: RepoPilotState
    ) -> _DocResult:
        structured_llm = self._llm.with_structured_output(_DocResult)
        result: _DocResult = invoke_with_retry(
            structured_llm,
            f"Update the module-level docstring for this Python file to reflect recent changes.\n\n"
            f"Objective that caused the change: {state['objective']}\n"
            f"File: {path}\n\n"
            f"Current content:\n```python\n{content}\n```\n\n"
            "Rules:\n"
            "- Keep the docstring concise (2-4 sentences).\n"
            "- In updated_content return the COMPLETE file with the new docstring in place.\n"
            "- migration_note: one sentence — what changed and why."
        )
        return result

    def _make_executor(self, state: RepoPilotState) -> ToolExecutor:
        load_all_tools()
        return ToolExecutor(registry, state)
