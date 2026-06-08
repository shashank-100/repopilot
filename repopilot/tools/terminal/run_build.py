from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.terminal._run import run


class RunBuildInput(ToolInput):
    repo_path: str
    command: str = "python -m build"
    timeout: int = 300


@tool("terminal.run_build", "Run a build command in a repository")
def run_build(inp: RunBuildInput) -> ToolOutput:
    try:
        cmd = inp.command.split()
        code, stdout, stderr = run(cmd, cwd=inp.repo_path, timeout=inp.timeout)
        return ToolOutput(
            success=code == 0,
            data={"returncode": code, "stdout": stdout, "stderr": stderr},
        )
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
