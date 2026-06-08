from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.terminal._run import run


class RunPipInstallInput(ToolInput):
    packages: list[str]
    cwd: str | None = None


@tool("terminal.run_pip_install", "Install Python packages via pip")
def run_pip_install(inp: RunPipInstallInput) -> ToolOutput:
    try:
        code, stdout, stderr = run(
            ["python", "-m", "pip", "install", *inp.packages],
            cwd=inp.cwd,
        )
        return ToolOutput(
            success=code == 0,
            data={"returncode": code, "stdout": stdout, "stderr": stderr},
        )
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
