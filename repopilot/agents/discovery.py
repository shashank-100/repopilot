"""Repository Discovery Agent — produces a RepositoryMap from the target repo."""
from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel

from repopilot.llm import default_llm, invoke_with_retry
from pydantic import BaseModel, Field

from repopilot.state import RepoPilotState
from repopilot.tools.executor import ToolExecutor

logger = structlog.get_logger(__name__)


class _RepositoryMapSchema(BaseModel):
    framework: str = Field(description="Primary framework detected (e.g. 'fastapi', 'django', 'none')")
    language: str = Field(default="python")
    key_files: list[dict[str, str]] = Field(description="List of {path, purpose} for important files")
    entry_points: list[str] = Field(description="Main entry point files (e.g. main.py, app.py)")
    test_dirs: list[str] = Field(description="Directories containing tests")
    config_files: list[str] = Field(description="Configuration files found")
    summary: str = Field(description="2-3 sentence summary of the repository purpose and structure")


class DiscoveryAgent:
    def __init__(self, llm: BaseChatModel | None = None, executor: ToolExecutor | None = None) -> None:
        self._llm = llm or default_llm()
        self._executor = executor

    def run(self, state: RepoPilotState) -> RepoPilotState:
        log = logger.bind(run_id=state["run_id"], agent="discovery")
        log.info("agent.start")

        executor = self._executor
        repo_path = state["repo_path"]

        # Gather raw signals via tools
        dir_tree: dict[str, Any] = {}
        frameworks: list[str] = []
        if executor:
            tree_result = executor.run("fs.list_directory", path=repo_path, depth=3)
            if tree_result.success:
                dir_tree = tree_result.data or {}

            fw_result = executor.run("analysis.detect_framework", repo_path=repo_path)
            if fw_result.success:
                frameworks = (fw_result.data or {}).get("frameworks", [])

        framework_hint = ", ".join(frameworks) if frameworks else "unknown"
        tree_text = str(dir_tree)[:3000]

        structured_llm = self._llm.with_structured_output(_RepositoryMapSchema)
        result: _RepositoryMapSchema = invoke_with_retry(
            structured_llm,
            f"Analyze this Python repository structure and produce a RepositoryMap.\n\n"
            f"Detected frameworks: {framework_hint}\n\n"
            f"Directory tree (truncated):\n{tree_text}\n\n"
            f"Repository path: {repo_path}"
        )

        state["repository_map"] = {
            "root_path": repo_path,
            "framework": result.framework,
            "language": result.language,
            "key_files": result.key_files,
            "entry_points": result.entry_points,
            "test_dirs": result.test_dirs,
            "config_files": result.config_files,
            "summary": result.summary,
        }
        state["current_phase"] = "discovery"
        state["observations"].append(f"Discovery: {result.summary}")
        log.info("agent.done", framework=result.framework)
        return state
