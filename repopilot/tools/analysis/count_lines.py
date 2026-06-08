from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class CountLinesInput(ToolInput):
    repo_path: str
    file_pattern: str = "**/*.py"


@tool("analysis.count_lines", "Count total lines of code matching a file pattern in a repo")
def count_lines(inp: CountLinesInput) -> ToolOutput:
    try:
        root = Path(inp.repo_path)
        total = 0
        file_counts: dict[str, int] = {}
        for p in root.glob(inp.file_pattern):
            if p.is_file():
                try:
                    n = sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))
                    file_counts[str(p)] = n
                    total += n
                except OSError:
                    pass
        return ToolOutput(success=True, data={"total_lines": total, "file_count": len(file_counts), "files": file_counts})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
