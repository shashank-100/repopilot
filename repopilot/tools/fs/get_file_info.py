import os
from datetime import datetime, timezone
from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class GetFileInfoInput(ToolInput):
    path: str


@tool("fs.get_file_info", "Get metadata about a file (size, modified time, line count)")
def get_file_info(inp: GetFileInfoInput) -> ToolOutput:
    try:
        p = Path(inp.path)
        stat = p.stat()
        line_count: int | None = None
        if p.is_file():
            try:
                line_count = sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
        return ToolOutput(success=True, data={
            "path": str(p),
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "line_count": line_count,
            "is_file": p.is_file(),
            "is_dir": p.is_dir(),
            "extension": p.suffix,
        })
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
