from repopilot.tools.analysis._parser import node_text, parse_file
from repopilot.tools.base import ToolInput, ToolOutput, tool


class FindImportsInput(ToolInput):
    path: str


@tool("analysis.find_imports", "Extract all import statements from a Python file")
def find_imports(inp: FindImportsInput) -> ToolOutput:
    try:
        root, src = parse_file(inp.path)
        imports: list[dict] = []

        def walk(node):
            if node.type == "import_statement":
                imports.append({"type": "import", "text": node_text(node, src)})
            elif node.type == "import_from_statement":
                imports.append({"type": "from", "text": node_text(node, src)})
            for child in node.children:
                walk(child)

        walk(root)
        return ToolOutput(success=True, data={"imports": imports, "count": len(imports)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
