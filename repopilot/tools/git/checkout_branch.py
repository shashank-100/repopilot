from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.git._run import git


class CheckoutBranchInput(ToolInput):
    repo_path: str
    branch_name: str


@tool("git.checkout_branch", "Check out an existing branch")
def checkout_branch(inp: CheckoutBranchInput) -> ToolOutput:
    try:
        git(inp.repo_path, "checkout", inp.branch_name)
        return ToolOutput(success=True, data={"branch": inp.branch_name})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
