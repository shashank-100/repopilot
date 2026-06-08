from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.git._run import git


class CreateBranchInput(ToolInput):
    repo_path: str
    branch_name: str
    from_ref: str = "HEAD"


@tool("git.create_branch", "Create a new git branch from a ref")
def create_branch(inp: CreateBranchInput) -> ToolOutput:
    try:
        git(inp.repo_path, "checkout", "-b", inp.branch_name, inp.from_ref)
        return ToolOutput(success=True, data={"branch": inp.branch_name})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
