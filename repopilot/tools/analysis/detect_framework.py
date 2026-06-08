"""Heuristic framework detection by inspecting dependency files."""
from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool

_FRAMEWORK_MARKERS = {
    "fastapi": ["fastapi"],
    "flask": ["flask"],
    "django": ["django"],
    "litestar": ["litestar"],
    "starlette": ["starlette"],
    "langchain": ["langchain"],
    "langgraph": ["langgraph"],
}


class DetectFrameworkInput(ToolInput):
    repo_path: str


@tool("analysis.detect_framework", "Detect which Python frameworks a repository uses")
def detect_framework(inp: DetectFrameworkInput) -> ToolOutput:
    try:
        root = Path(inp.repo_path)
        dependency_text = ""
        for dep_file in ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"]:
            p = root / dep_file
            if p.exists():
                dependency_text += p.read_text(encoding="utf-8", errors="ignore").lower()

        detected = [
            fw for fw, markers in _FRAMEWORK_MARKERS.items()
            if any(m in dependency_text for m in markers)
        ]
        return ToolOutput(success=True, data={"frameworks": detected})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
