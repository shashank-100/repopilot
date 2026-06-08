import re
from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool

_TODO_RE = re.compile(r"#\s*TODO[:\s].*", re.IGNORECASE)


class FindTodosInput(ToolInput):
    repo_path: str
    max_results: int = 100


@tool("research.find_todos", "Find all TODO comments in a repository")
def find_todos(inp: FindTodosInput) -> ToolOutput:
    try:
        root = Path(inp.repo_path)
        results: list[dict] = []
        for py_file in root.glob("**/*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                for lineno, line in enumerate(py_file.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if _TODO_RE.search(line):
                        results.append({"file": str(py_file), "line": lineno, "text": line.strip()})
                        if len(results) >= inp.max_results:
                            return ToolOutput(success=True, data={"todos": results, "truncated": True})
            except OSError:
                continue
        return ToolOutput(success=True, data={"todos": results, "truncated": False})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
