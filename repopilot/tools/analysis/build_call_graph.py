"""Best-effort call graph: function definitions → call expressions within each function."""
from repopilot.tools.analysis._parser import node_text, parse_file
from repopilot.tools.base import ToolInput, ToolOutput, tool


class BuildCallGraphInput(ToolInput):
    path: str


@tool("analysis.build_call_graph", "Build a function-level call graph for a single Python file")
def build_call_graph(inp: BuildCallGraphInput) -> ToolOutput:
    try:
        root, src = parse_file(inp.path)
        edges: list[dict] = []
        current_fn: list[str] = []

        def walk(node):
            if node.type in ("function_definition", "async_function_definition"):
                name_node = node.child_by_field_name("name")
                fn_name = node_text(name_node, src) if name_node else "<unknown>"
                current_fn.append(fn_name)
                for child in node.children:
                    walk(child)
                current_fn.pop()
                return
            if node.type == "call" and current_fn:
                fn_node = node.child_by_field_name("function")
                if fn_node:
                    callee = node_text(fn_node, src)
                    edges.append({"caller": current_fn[-1], "callee": callee, "line": node.start_point[0] + 1})
            for child in node.children:
                walk(child)

        walk(root)
        return ToolOutput(success=True, data={"edges": edges, "count": len(edges)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
