"""Search docstrings and comments in a repository."""
import re
from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool

_DOCSTRING_PATTERN = re.compile(r'""".*?"""|\'\'\'.*?\'\'\'', re.DOTALL)
_COMMENT_PATTERN = re.compile(r"#.*")


class SearchDocsInput(ToolInput):
    repo_path: str
    query: str
    case_sensitive: bool = False
    max_results: int = 50


@tool("research.search_docs", "Search docstrings and inline comments for a query term")
def search_docs(inp: SearchDocsInput) -> ToolOutput:
    try:
        flags = 0 if inp.case_sensitive else re.IGNORECASE
        regex = re.compile(re.escape(inp.query), flags)
        root = Path(inp.repo_path)
        results: list[dict] = []

        for py_file in root.glob("**/*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in _DOCSTRING_PATTERN.finditer(text):
                if regex.search(match.group()):
                    line = text[:match.start()].count("\n") + 1
                    results.append({"file": str(py_file), "line": line, "type": "docstring", "text": match.group()[:200]})
            for lineno, line in enumerate(text.splitlines(), 1):
                m = _COMMENT_PATTERN.search(line)
                if m and regex.search(m.group()):
                    results.append({"file": str(py_file), "line": lineno, "type": "comment", "text": line.strip()})
            if len(results) >= inp.max_results:
                break

        return ToolOutput(success=True, data={"results": results[:inp.max_results], "count": len(results)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
