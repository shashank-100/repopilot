from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.git._run import git


class GitLogInput(ToolInput):
    repo_path: str
    n: int = 20
    oneline: bool = True


@tool("git.git_log", "Return the recent commit log of a repository")
def git_log(inp: GitLogInput) -> ToolOutput:
    try:
        fmt = "--oneline" if inp.oneline else "--format=%H %an %ai %s"
        _, out, _ = git(inp.repo_path, "log", fmt, f"-{inp.n}")
        return ToolOutput(success=True, data={"log": out, "commits": out.splitlines()})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
