from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.git._run import git


class GitStashPopInput(ToolInput):
    repo_path: str


@tool("git.git_stash_pop", "Pop the most recent stash entry")
def git_stash_pop(inp: GitStashPopInput) -> ToolOutput:
    try:
        _, out, _ = git(inp.repo_path, "stash", "pop")
        return ToolOutput(success=True, data={"output": out.strip()})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
