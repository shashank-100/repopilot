from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class DeleteFileInput(ToolInput):
    path: str
    missing_ok: bool = False


@tool("fs.delete_file", "Delete a file from the filesystem")
def delete_file(inp: DeleteFileInput) -> ToolOutput:
    try:
        Path(inp.path).unlink(missing_ok=inp.missing_ok)
        return ToolOutput(success=True, data={"path": inp.path})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
