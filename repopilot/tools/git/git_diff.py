from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.git._run import git


class GitDiffInput(ToolInput):
    repo_path: str
    ref: str = "HEAD"
    path: str | None = None


@tool("git.git_diff", "Show the diff of working tree (or against a ref) for a repo")
def git_diff(inp: GitDiffInput) -> ToolOutput:
    try:
        args = ["diff", inp.ref]
        if inp.path:
            args += ["--", inp.path]
        _, out, _ = git(inp.repo_path, *args)
        return ToolOutput(success=True, data={"diff": out})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
