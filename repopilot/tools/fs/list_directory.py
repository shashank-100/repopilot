from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class ListDirectoryInput(ToolInput):
    path: str
    depth: int = 2
    include_hidden: bool = False


def _walk(p: Path, depth: int, include_hidden: bool) -> list[dict]:
    entries = []
    try:
        for child in sorted(p.iterdir()):
            if not include_hidden and child.name.startswith("."):
                continue
            entry = {"path": str(child), "type": "dir" if child.is_dir() else "file"}
            if child.is_dir() and depth > 1:
                entry["children"] = _walk(child, depth - 1, include_hidden)
            entries.append(entry)
    except PermissionError:
        pass
    return entries


@tool("fs.list_directory", "List directory contents up to a given depth")
def list_directory(inp: ListDirectoryInput) -> ToolOutput:
    try:
        tree = _walk(Path(inp.path), inp.depth, inp.include_hidden)
        return ToolOutput(success=True, data={"tree": tree})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
