from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class MakeDirectoryInput(ToolInput):
    path: str
    exist_ok: bool = True


@tool("fs.make_directory", "Create a directory (and parents) at the given path")
def make_directory(inp: MakeDirectoryInput) -> ToolOutput:
    try:
        Path(inp.path).mkdir(parents=True, exist_ok=inp.exist_ok)
        return ToolOutput(success=True, data={"path": inp.path})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
