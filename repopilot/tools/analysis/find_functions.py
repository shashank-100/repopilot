from repopilot.tools.analysis._parser import node_text, parse_file
from repopilot.tools.base import ToolInput, ToolOutput, tool


class FindFunctionsInput(ToolInput):
    path: str
    include_private: bool = True


@tool("analysis.find_functions", "Extract all function/method definitions from a Python file")
def find_functions(inp: FindFunctionsInput) -> ToolOutput:
    try:
        root, src = parse_file(inp.path)
        functions: list[dict] = []

        def walk(node):
            if node.type in ("function_definition", "async_function_definition"):
                name_node = node.child_by_field_name("name")
                name = node_text(name_node, src) if name_node else ""
                if not inp.include_private and name.startswith("_"):
                    for child in node.children:
                        walk(child)
                    return
                params_node = node.child_by_field_name("parameters")
                functions.append({
                    "name": name,
                    "params": node_text(params_node, src) if params_node else "",
                    "line": node.start_point[0] + 1,
                    "async": node.type == "async_function_definition",
                })
            for child in node.children:
                walk(child)

        walk(root)
        return ToolOutput(success=True, data={"functions": functions, "count": len(functions)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
