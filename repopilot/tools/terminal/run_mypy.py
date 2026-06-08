from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.terminal._run import run


class RunMypyInput(ToolInput):
    repo_path: str
    paths: list[str] = ["."]
    args: list[str] = []


@tool("terminal.run_mypy", "Run mypy type checking in a repository")
def run_mypy(inp: RunMypyInput) -> ToolOutput:
    try:
        code, stdout, stderr = run(
            ["python", "-m", "mypy", *inp.paths, *inp.args],
            cwd=inp.repo_path,
        )
        return ToolOutput(
            success=code == 0,
            data={"returncode": code, "stdout": stdout, "stderr": stderr},
        )
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
