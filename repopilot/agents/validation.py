"""Validation Agent (Phase 11) — runs pytest, mypy, ruff against the repo.

Stores a structured ValidationResult in state. The workflow's conditional
edge after this node reads state["validation_results"]["passed"] to decide
whether to route to documentation (pass) or reflection (repair).
"""
from __future__ import annotations

from pathlib import Path

import structlog

from repopilot.state import RepoPilotState, ValidationResult
from repopilot.tools.base import load_all_tools, registry
from repopilot.tools.executor import ToolExecutor

logger = structlog.get_logger(__name__)

# Config files that signal a tool is intentionally configured for the repo
_MYPY_CONFIGS = ["mypy.ini", ".mypy.ini", "setup.cfg", "pyproject.toml"]
_RUFF_CONFIGS = ["ruff.toml", ".ruff.toml", "pyproject.toml", "setup.cfg"]


def _has_config(repo: str, candidates: list[str], section: str = "") -> bool:
    """Return True if the repo has a config file enabling the tool."""
    root = Path(repo)
    for name in candidates:
        p = root / name
        if not p.exists():
            continue
        if name in ("pyproject.toml", "setup.cfg") and section:
            try:
                if section in p.read_text(encoding="utf-8", errors="ignore"):
                    return True
            except OSError:
                continue
        else:
            return True
    return False


class ValidationAgent:
    def __init__(self, executor: ToolExecutor | None = None) -> None:
        self._executor = executor

    def run(self, state: RepoPilotState) -> RepoPilotState:
        log = logger.bind(run_id=state["run_id"], agent="validation")
        log.info("agent.start")

        executor = self._executor or self._make_executor(state)
        repo = state["repo_path"]
        errors: list[str] = []

        # --- scope check: did implementation touch files outside the plan? ---
        plan = state.get("execution_plan", {})
        planned: set[str] = set()
        for step in plan.get("steps", []):
            for f in step.get("files_to_modify", []):
                planned.add(f.split("/")[-1])  # compare by basename
        out_of_scope = [
            f for f in state.get("modified_files", [])
            if planned and f.split("/")[-1] not in planned
        ]
        if out_of_scope:
            names = ", ".join(p.split("/")[-1] for p in out_of_scope)
            state["observations"].append(
                f"validation: ⚠ {len(out_of_scope)} file(s) modified outside the plan: {names}"
            )
            log.warning("validation.out_of_scope", files=out_of_scope)

        # --- pytest ---
        pytest_res = executor.run("terminal.run_pytest", repo_path=repo, args=[])
        rc = (pytest_res.data or {}).get("returncode")
        pytest_out = (pytest_res.data or {}).get("stdout", "") + (pytest_res.data or {}).get("stderr", "")
        # rc 0 = pass, rc 5 = "no tests collected" (not a failure for our purposes).
        # Any other non-zero rc is a real test failure.
        if rc not in (0, 5):
            errors.append(f"pytest failed (rc={rc})")

        # --- mypy (only if the repo configures it) ---
        mypy_out = ""
        if _has_config(repo, _MYPY_CONFIGS, section="[tool.mypy]"):
            mypy_res = executor.run("terminal.run_mypy", repo_path=repo, paths=["."])
            mypy_out = (mypy_res.data or {}).get("stdout", "") + (mypy_res.data or {}).get("stderr", "")
            if not mypy_res.success:
                errors.append("mypy reported type errors")
        else:
            log.info("validation.skip_mypy", reason="no mypy config in repo")

        # --- ruff (only if the repo configures it) ---
        ruff_out = ""
        if _has_config(repo, _RUFF_CONFIGS, section="[tool.ruff]"):
            ruff_res = executor.run("terminal.run_ruff", repo_path=repo, paths=["."])
            ruff_out = (ruff_res.data or {}).get("stdout", "") + (ruff_res.data or {}).get("stderr", "")
            if not ruff_res.success:
                errors.append("ruff reported lint errors")
        else:
            log.info("validation.skip_ruff", reason="no ruff config in repo")

        passed = len(errors) == 0
        result: ValidationResult = {
            "passed": passed,
            "pytest_output": pytest_out[:4000],
            "mypy_output": mypy_out[:2000],
            "ruff_output": ruff_out[:2000],
            "errors": errors,
        }

        state["validation_results"] = result
        state["current_phase"] = "validation"
        status = "passed" if passed else f"failed ({', '.join(errors)})"
        state["observations"].append(f"validation: {status}")
        log.info("agent.done", passed=passed, error_count=len(errors))
        return state

    def _make_executor(self, state: RepoPilotState) -> ToolExecutor:
        load_all_tools()
        return ToolExecutor(registry, state)
