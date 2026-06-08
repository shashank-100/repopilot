from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class AppendFileInput(ToolInput):
    path: str
    content: str


@tool("fs.append_file", "Append content to the end of a file")
def append_file(inp: AppendFileInput) -> ToolOutput:
    try:
        p = Path(inp.path)
        with p.open("a", encoding="utf-8") as f:
            f.write(inp.content)
        return ToolOutput(success=True, data={"path": str(p)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
