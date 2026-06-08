from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.terminal._run import run


class RunPytestInput(ToolInput):
    repo_path: str
    args: list[str] = []
    timeout: int = 120


@tool("terminal.run_pytest", "Run pytest in a repository and return the output")
def run_pytest(inp: RunPytestInput) -> ToolOutput:
    try:
        code, stdout, stderr = run(
            ["python", "-m", "pytest", *inp.args, "--tb=short", "-q"],
            cwd=inp.repo_path,
            timeout=inp.timeout,
        )
        return ToolOutput(
            success=code == 0,
            data={"returncode": code, "stdout": stdout, "stderr": stderr},
        )
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
