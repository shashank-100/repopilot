"""Approximate cyclomatic complexity by counting branching nodes."""
from repopilot.tools.analysis._parser import parse_file
from repopilot.tools.base import ToolInput, ToolOutput, tool

_BRANCH_TYPES = {
    "if_statement", "elif_clause", "for_statement", "while_statement",
    "except_clause", "with_statement", "conditional_expression",
    "boolean_operator",
}


class GetFileComplexityInput(ToolInput):
    path: str


@tool("analysis.get_file_complexity", "Estimate cyclomatic complexity of a Python file")
def get_file_complexity(inp: GetFileComplexityInput) -> ToolOutput:
    try:
        root, _ = parse_file(inp.path)
        count = 0

        def walk(node):
            nonlocal count
            if node.type in _BRANCH_TYPES:
                count += 1
            for child in node.children:
                walk(child)

        walk(root)
        return ToolOutput(success=True, data={"complexity": count + 1, "branch_count": count})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
