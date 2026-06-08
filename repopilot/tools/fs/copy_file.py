import shutil
from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class CopyFileInput(ToolInput):
    src: str
    dst: str
    create_parents: bool = True


@tool("fs.copy_file", "Copy a file from src to dst")
def copy_file(inp: CopyFileInput) -> ToolOutput:
    try:
        dst = Path(inp.dst)
        if inp.create_parents:
            dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(inp.src, dst)
        return ToolOutput(success=True, data={"src": inp.src, "dst": str(dst)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
