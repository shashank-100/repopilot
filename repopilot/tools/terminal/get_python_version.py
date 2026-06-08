from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.terminal._run import run


class GetPythonVersionInput(ToolInput):
    cwd: str | None = None


@tool("terminal.get_python_version", "Return the Python interpreter version")
def get_python_version(inp: GetPythonVersionInput) -> ToolOutput:
    try:
        code, stdout, stderr = run(["python", "--version"], cwd=inp.cwd)
        version = (stdout or stderr).strip()
        return ToolOutput(success=code == 0, data={"version": version})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
