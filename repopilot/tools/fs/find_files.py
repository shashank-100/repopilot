from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class FindFilesInput(ToolInput):
    root: str
    pattern: str = "**/*"
    max_results: int = 500
    exclude_dirs: list[str] = [".git", "__pycache__", "node_modules", ".venv", "venv"]


@tool("fs.find_files", "Find files matching a glob pattern under a root directory")
def find_files(inp: FindFilesInput) -> ToolOutput:
    try:
        root = Path(inp.root)
        matches: list[str] = []
        for p in root.glob(inp.pattern):
            if any(part in inp.exclude_dirs for part in p.parts):
                continue
            if p.is_file():
                matches.append(str(p))
            if len(matches) >= inp.max_results:
                break
        return ToolOutput(success=True, data={"files": matches, "count": len(matches)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
