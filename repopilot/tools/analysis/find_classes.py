from repopilot.tools.analysis._parser import node_text, parse_file
from repopilot.tools.base import ToolInput, ToolOutput, tool


class FindClassesInput(ToolInput):
    path: str


@tool("analysis.find_classes", "Extract all class definitions from a Python file")
def find_classes(inp: FindClassesInput) -> ToolOutput:
    try:
        root, src = parse_file(inp.path)
        classes: list[dict] = []

        def walk(node):
            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                bases_node = node.child_by_field_name("superclasses")
                classes.append({
                    "name": node_text(name_node, src) if name_node else "",
                    "bases": node_text(bases_node, src) if bases_node else "",
                    "line": node.start_point[0] + 1,
                })
            for child in node.children:
                walk(child)

        walk(root)
        return ToolOutput(success=True, data={"classes": classes, "count": len(classes)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
