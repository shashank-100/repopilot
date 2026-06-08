import re
from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool

_FIXME_RE = re.compile(r"#\s*FIXME[:\s].*", re.IGNORECASE)


class FindFixmesInput(ToolInput):
    repo_path: str
    max_results: int = 100


@tool("research.find_fixmes", "Find all FIXME comments in a repository")
def find_fixmes(inp: FindFixmesInput) -> ToolOutput:
    try:
        root = Path(inp.repo_path)
        results: list[dict] = []
        for py_file in root.glob("**/*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                for lineno, line in enumerate(py_file.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if _FIXME_RE.search(line):
                        results.append({"file": str(py_file), "line": lineno, "text": line.strip()})
                        if len(results) >= inp.max_results:
                            return ToolOutput(success=True, data={"fixmes": results, "truncated": True})
            except OSError:
                continue
        return ToolOutput(success=True, data={"fixmes": results, "truncated": False})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
