from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.terminal._run import run


class RunRuffFormatInput(ToolInput):
    repo_path: str
    paths: list[str] = ["."]
    check_only: bool = False


@tool("terminal.run_ruff_format", "Run ruff formatter (optionally in check-only mode)")
def run_ruff_format(inp: RunRuffFormatInput) -> ToolOutput:
    try:
        args = ["python", "-m", "ruff", "format", *inp.paths]
        if inp.check_only:
            args.append("--check")
        code, stdout, stderr = run(args, cwd=inp.repo_path)
        return ToolOutput(
            success=code == 0,
            data={"returncode": code, "stdout": stdout, "stderr": stderr},
        )
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
