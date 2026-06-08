from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.git._run import git


class GetCurrentBranchInput(ToolInput):
    repo_path: str


@tool("git.get_current_branch", "Return the name of the currently checked-out branch")
def get_current_branch(inp: GetCurrentBranchInput) -> ToolOutput:
    try:
        _, out, _ = git(inp.repo_path, "rev-parse", "--abbrev-ref", "HEAD")
        return ToolOutput(success=True, data={"branch": out.strip()})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
