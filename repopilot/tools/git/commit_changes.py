from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.git._run import git


class CommitChangesInput(ToolInput):
    repo_path: str
    message: str
    add_all: bool = True


@tool("git.commit_changes", "Stage and commit changes in a repository")
def commit_changes(inp: CommitChangesInput) -> ToolOutput:
    try:
        if inp.add_all:
            git(inp.repo_path, "add", "-A")
        _, out, _ = git(inp.repo_path, "commit", "-m", inp.message)
        return ToolOutput(success=True, data={"output": out.strip()})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
