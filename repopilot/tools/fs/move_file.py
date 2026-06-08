import shutil
from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class MoveFileInput(ToolInput):
    src: str
    dst: str
    create_parents: bool = True


@tool("fs.move_file", "Move or rename a file")
def move_file(inp: MoveFileInput) -> ToolOutput:
    try:
        dst = Path(inp.dst)
        if inp.create_parents:
            dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(inp.src, str(dst))
        return ToolOutput(success=True, data={"src": inp.src, "dst": str(dst)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
