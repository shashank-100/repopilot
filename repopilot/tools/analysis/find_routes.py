"""Detect FastAPI / Flask route decorators in Python files."""
import re
from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool

_ROUTE_PATTERN = re.compile(
    r'@\w+\.(get|post|put|patch|delete|head|options|websocket)\s*\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)


class FindRoutesInput(ToolInput):
    path: str


@tool("analysis.find_routes", "Detect HTTP route decorators (FastAPI/Flask) in a Python file")
def find_routes(inp: FindRoutesInput) -> ToolOutput:
    try:
        lines = Path(inp.path).read_text(encoding="utf-8", errors="ignore").splitlines()
        routes: list[dict] = []
        for lineno, line in enumerate(lines, 1):
            m = _ROUTE_PATTERN.search(line)
            if m:
                routes.append({
                    "method": m.group(1).upper(),
                    "path": m.group(2),
                    "line": lineno,
                    "file": inp.path,
                })
        return ToolOutput(success=True, data={"routes": routes, "count": len(routes)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
