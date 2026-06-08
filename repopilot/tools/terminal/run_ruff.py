from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.terminal._run import run


class RunRuffInput(ToolInput):
    repo_path: str
    paths: list[str] = ["."]


@tool("terminal.run_ruff", "Run ruff linter in a repository")
def run_ruff(inp: RunRuffInput) -> ToolOutput:
    try:
        code, stdout, stderr = run(
            ["python", "-m", "ruff", "check", *inp.paths],
            cwd=inp.repo_path,
        )
        return ToolOutput(
            success=code == 0,
            data={"returncode": code, "stdout": stdout, "stderr": stderr},
        )
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
