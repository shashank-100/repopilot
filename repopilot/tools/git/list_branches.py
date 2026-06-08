from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.git._run import git


class ListBranchesInput(ToolInput):
    repo_path: str
    include_remote: bool = False


@tool("git.list_branches", "List all local (and optionally remote) branches")
def list_branches(inp: ListBranchesInput) -> ToolOutput:
    try:
        args = ["branch", "-a"] if inp.include_remote else ["branch"]
        _, out, _ = git(inp.repo_path, *args)
        branches = [b.strip().lstrip("* ") for b in out.splitlines() if b.strip()]
        return ToolOutput(success=True, data={"branches": branches})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
