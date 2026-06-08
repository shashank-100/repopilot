from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.git._run import git


class GitStashInput(ToolInput):
    repo_path: str
    message: str = ""


@tool("git.git_stash", "Stash the current working tree changes")
def git_stash(inp: GitStashInput) -> ToolOutput:
    try:
        args = ["stash", "push"]
        if inp.message:
            args += ["-m", inp.message]
        _, out, _ = git(inp.repo_path, *args)
        return ToolOutput(success=True, data={"output": out.strip()})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
