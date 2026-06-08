from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class ReadFileInput(ToolInput):
    path: str
    start_line: int | None = None
    end_line: int | None = None


@tool("fs.read_file", "Read file contents, optionally restricted to a line range")
def read_file(inp: ReadFileInput) -> ToolOutput:
    try:
        lines = Path(inp.path).read_text(encoding="utf-8").splitlines(keepends=True)
        start = (inp.start_line or 1) - 1
        end = inp.end_line or len(lines)
        content = "".join(lines[start:end])
        return ToolOutput(success=True, data={"content": content, "total_lines": len(lines)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
