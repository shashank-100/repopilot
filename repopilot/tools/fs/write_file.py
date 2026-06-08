from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class WriteFileInput(ToolInput):
    path: str
    content: str
    create_parents: bool = True


@tool("fs.write_file", "Write content to a file, creating parent directories if needed")
def write_file(inp: WriteFileInput) -> ToolOutput:
    try:
        p = Path(inp.path)
        if inp.create_parents:
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(inp.content, encoding="utf-8")
        return ToolOutput(success=True, data={"path": str(p), "bytes": len(inp.content.encode())})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
