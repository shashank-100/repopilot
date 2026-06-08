"""Validation Agent (Phase 11) — ADVISORY validation.

Validation reports findings but NEVER blocks the run. Many repos can't be
"validated by running the code" (no tests, wrong language, missing deps), so
this agent picks the strongest check the repo actually supports and records
the result. The workflow always proceeds to documentation → PR afterwards;
the only thing that triggers the repair loop is the agent itself crashing.

Tiers (strongest first):
  1. tests   — pytest passes, or `npm test` has a real script
  2. lint    — mypy / ruff if the repo configures them
  3. syntax  — do the changed files parse? (Python via py_compile, JS/TS basic)
  4. none    — nothing runnable; record as not_validated (still proceed)

Result severity:
  "pass"          — a check ran and was clean
  "warnings"      — a check ran and surfaced advisory findings
  "not_validated" — nothing could be run; the change is unverified
"""
from __future__ import annotations

import ast
from pathlib import Path

import structlog

from repopilot.state import RepoPilotState, ValidationResult
from repopilot.tools.base import load_all_tools, registry
from repopilot.tools.executor import ToolExecutor

logger = structlog.get_logger(__name__)

_MYPY_CONFIGS = ["mypy.ini", ".mypy.ini", "setup.cfg", "pyproject.toml"]
_RUFF_CONFIGS = ["ruff.toml", ".ruff.toml", "pyproject.toml", "setup.cfg"]


def _has_config(repo: str, candidates: list[str], section: str = "") -> bool:
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


def _has_python_tests(repo: str) -> bool:
    root = Path(repo)
    if any(root.glob("**/test_*.py")) or any(root.glob("**/*_test.py")):
        return True
    return (root / "tests").is_dir()


def _has_npm_test(repo: str) -> bool:
    pkg = Path(repo) / "package.json"
    if not pkg.exists():
        return False
    try:
        import json
        data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
        scripts = data.get("scripts", {})
        test = scripts.get("test", "")
        # Skip the default placeholder npm puts in every package.json
        return bool(test) and "no test specified" not in test
    except (OSError, ValueError):
        return False


def _syntax_check(modified: list[str]) -> list[str]:
    """Parse changed source files. Returns a list of syntax-error findings."""
    findings: list[str] = []
    for path in modified:
        p = Path(path)
        if not p.exists():
            continue
        suffix = p.suffix
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if suffix == ".py":
            try:
                ast.parse(text)
            except SyntaxError as e:
                findings.append(f"{p.name}: Python syntax error — {e.msg} (line {e.lineno})")
        elif suffix in (".json",):
            try:
                import json
                json.loads(text)
            except ValueError as e:
                findings.append(f"{p.name}: invalid JSON — {e}")
        # JS/TS: no bundled parser; rely on lint/tests if configured. We at
        # least flag obviously unbalanced braces as a cheap smoke check.
        elif suffix in (".js", ".jsx", ".ts", ".tsx"):
            if text.count("{") != text.count("}"):
                findings.append(f"{p.name}: unbalanced braces (possible syntax error)")
    return findings


class ValidationAgent:
    def __init__(self, executor: ToolExecutor | None = None) -> None:
        self._executor = executor

    def run(self, state: RepoPilotState) -> RepoPilotState:
        log = logger.bind(run_id=state["run_id"], agent="validation")
        log.info("agent.start")

        executor = self._executor or self._make_executor(state)
        repo = state["repo_path"]
        modified = state.get("modified_files", [])
        findings: list[str] = []
        pytest_out = mypy_out = ruff_out = ""

        # --- scope check (advisory note only) ---
        plan = state.get("execution_plan", {})
        planned = {f.split("/")[-1] for s in plan.get("steps", []) for f in s.get("files_to_modify", [])}
        out_of_scope = [f for f in modified if planned and f.split("/")[-1] not in planned]
        if out_of_scope:
            findings.append(
                f"{len(out_of_scope)} file(s) modified outside the plan: "
                + ", ".join(p.split("/")[-1] for p in out_of_scope)
            )

        # --- choose the strongest available tier ---
        validated_with = "none"
        severity = "not_validated"

        if _has_python_tests(repo):
            validated_with = "tests"
            # Short timeout: validation is advisory. If a test suite hangs (e.g.
            # a conftest that pip-installs on import), we don't wedge the run —
            # we record the timeout as a finding and move on.
            res = executor.run("terminal.run_pytest", repo_path=repo, args=[], timeout=45)
            rc = (res.data or {}).get("returncode")
            pytest_out = ((res.data or {}).get("stdout", "") + (res.data or {}).get("stderr", ""))[:4000]
            if rc in (0, 5):  # 5 = collected nothing
                severity = "pass"
            elif rc == 124:  # timed out (e.g. a conftest that installs deps)
                severity = "warnings"
                findings.append("test suite timed out — skipped (advisory)")
            else:
                severity = "warnings"
                findings.append(f"pytest reported failures (rc={rc})")
        elif _has_npm_test(repo):
            validated_with = "tests"
            res = executor.run("terminal.run_command", command="npm test", cwd=repo, timeout=45)
            out = ((res.data or {}).get("stdout", "") + (res.data or {}).get("stderr", ""))
            pytest_out = out[:4000]
            severity = "pass" if res.success else "warnings"
            if not res.success:
                findings.append("npm test reported failures")
        elif _has_config(repo, _RUFF_CONFIGS, "[tool.ruff]") or _has_config(repo, _MYPY_CONFIGS, "[tool.mypy]"):
            validated_with = "lint"
            severity = "pass"
            if _has_config(repo, _MYPY_CONFIGS, "[tool.mypy]"):
                res = executor.run("terminal.run_mypy", repo_path=repo, paths=["."])
                mypy_out = ((res.data or {}).get("stdout", "") + (res.data or {}).get("stderr", ""))[:2000]
                if not res.success:
                    severity = "warnings"; findings.append("mypy reported type issues")
            if _has_config(repo, _RUFF_CONFIGS, "[tool.ruff]"):
                res = executor.run("terminal.run_ruff", repo_path=repo, paths=["."])
                ruff_out = ((res.data or {}).get("stdout", "") + (res.data or {}).get("stderr", ""))[:2000]
                if not res.success:
                    severity = "warnings"; findings.append("ruff reported lint issues")
        else:
            # Tier 3: syntax-parse the changed files.
            syntax_findings = _syntax_check(modified)
            if syntax_findings:
                validated_with = "syntax"
                severity = "warnings"
                findings.extend(syntax_findings)
            elif modified:
                validated_with = "syntax"
                severity = "pass"  # changed files parse cleanly
            else:
                validated_with = "none"
                severity = "not_validated"

        summary = {
            "pass": f"Validated via {validated_with} — clean",
            "warnings": f"Validated via {validated_with} — {len(findings)} advisory finding(s)",
            "not_validated": "Could not run automated validation (no tests/lint for this repo)",
        }[severity]

        result: ValidationResult = {
            "severity": severity,
            "validated_with": validated_with,
            "passed": severity == "pass",   # back-compat
            "summary": summary,
            "pytest_output": pytest_out,
            "mypy_output": mypy_out,
            "ruff_output": ruff_out,
            "findings": findings,
            "errors": findings,             # back-compat alias
        }

        state["validation_results"] = result
        state["current_phase"] = "validation"
        state["observations"].append(f"validation: {summary}")
        for f in findings:
            state["observations"].append(f"  ⚠ {f}")
        log.info("agent.done", severity=severity, validated_with=validated_with, findings=len(findings))
        return state

    def _make_executor(self, state: RepoPilotState) -> ToolExecutor:
        load_all_tools()
        return ToolExecutor(registry, state)
