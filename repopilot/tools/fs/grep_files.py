import re
from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class GrepFilesInput(ToolInput):
    root: str
    pattern: str
    file_pattern: str = "**/*.py"
    case_sensitive: bool = True
    max_results: int = 200


class GrepMatch(dict):
    pass


@tool("fs.grep_files", "Search for a regex pattern in files under a directory")
def grep_files(inp: GrepFilesInput) -> ToolOutput:
    try:
        flags = 0 if inp.case_sensitive else re.IGNORECASE
        regex = re.compile(inp.pattern, flags)
        root = Path(inp.root)
        results: list[dict] = []

        for path in root.glob(inp.file_pattern):
            if not path.is_file():
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, 1):
                if regex.search(line):
                    results.append({"file": str(path), "line": lineno, "text": line.rstrip()})
                    if len(results) >= inp.max_results:
                        return ToolOutput(success=True, data={"matches": results, "truncated": True})

        return ToolOutput(success=True, data={"matches": results, "truncated": False})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
