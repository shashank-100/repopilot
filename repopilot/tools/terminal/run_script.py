from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.terminal._run import run


class RunScriptInput(ToolInput):
    script_path: str
    args: list[str] = []
    cwd: str | None = None
    timeout: int = 60


@tool("terminal.run_script", "Execute a Python script file")
def run_script(inp: RunScriptInput) -> ToolOutput:
    try:
        code, stdout, stderr = run(
            ["python", inp.script_path, *inp.args],
            cwd=inp.cwd,
            timeout=inp.timeout,
        )
        return ToolOutput(
            success=code == 0,
            data={"returncode": code, "stdout": stdout, "stderr": stderr},
        )
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
