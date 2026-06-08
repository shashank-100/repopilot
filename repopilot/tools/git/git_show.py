from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.git._run import git


class GitShowInput(ToolInput):
    repo_path: str
    ref: str = "HEAD"


@tool("git.git_show", "Show the contents and metadata of a specific commit")
def git_show(inp: GitShowInput) -> ToolOutput:
    try:
        _, out, _ = git(inp.repo_path, "show", "--stat", inp.ref)
        return ToolOutput(success=True, data={"output": out})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
