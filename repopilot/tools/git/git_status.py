from repopilot.tools.base import ToolInput, ToolOutput, tool
from repopilot.tools.git._run import git


class GitStatusInput(ToolInput):
    repo_path: str


@tool("git.git_status", "Return the working tree status of a git repository")
def git_status(inp: GitStatusInput) -> ToolOutput:
    try:
        _, out, _ = git(inp.repo_path, "status", "--porcelain")
        lines = [l for l in out.splitlines() if l.strip()]
        return ToolOutput(success=True, data={"status": out, "changed_files": lines})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
