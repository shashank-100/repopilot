import shlex

from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.terminal._run import run


class RunCommandInput(ToolInput):
    command: str
    cwd: str | None = None
    timeout: int = 60


@tool("terminal.run_command", "Run an arbitrary shell command and return stdout/stderr")
def run_command(inp: RunCommandInput) -> ToolOutput:
    try:
        cmd = shlex.split(inp.command)
        code, stdout, stderr = run(cmd, cwd=inp.cwd, timeout=inp.timeout)
        return ToolOutput(
            success=code == 0,
            data={"returncode": code, "stdout": stdout, "stderr": stderr},
        )
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
