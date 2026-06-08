from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class FileExistsInput(ToolInput):
    path: str


@tool("fs.file_exists", "Check whether a file or directory exists")
def file_exists(inp: FileExistsInput) -> ToolOutput:
    p = Path(inp.path)
    return ToolOutput(success=True, data={"exists": p.exists(), "is_file": p.is_file(), "is_dir": p.is_dir()})
