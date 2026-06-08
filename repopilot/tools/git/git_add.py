from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.git._run import git


class GitAddInput(ToolInput):
    repo_path: str
    paths: list[str] = ["."]


@tool("git.git_add", "Stage specific files (or all) in a repository")
def git_add(inp: GitAddInput) -> ToolOutput:
    try:
        git(inp.repo_path, "add", *inp.paths)
        return ToolOutput(success=True, data={"staged": inp.paths})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
