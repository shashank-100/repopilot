"""Detect Pydantic BaseModel / SQLAlchemy / dataclass definitions."""
from repopilot.tools.analysis._parser import node_text, parse_file
from repopilot.tools.base import ToolInput, ToolOutput, tool

_MODEL_BASES = {"BaseModel", "Base", "DeclarativeBase", "SQLModel"}


class FindModelsInput(ToolInput):
    path: str


@tool("analysis.find_models", "Find Pydantic / SQLAlchemy model class definitions in a Python file")
def find_models(inp: FindModelsInput) -> ToolOutput:
    try:
        root, src = parse_file(inp.path)
        models: list[dict] = []

        def walk(node):
            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                bases_node = node.child_by_field_name("superclasses")
                name = node_text(name_node, src) if name_node else ""
                bases_text = node_text(bases_node, src) if bases_node else ""
                is_dataclass = False
                for child in node.children:
                    if child.type == "decorator" and "dataclass" in node_text(child, src):
                        is_dataclass = True
                if is_dataclass or any(b in bases_text for b in _MODEL_BASES):
                    kind = "dataclass" if is_dataclass else (
                        "sqlalchemy" if any(b in bases_text for b in {"Base", "DeclarativeBase"})
                        else "pydantic"
                    )
                    models.append({
                        "name": name,
                        "type": kind,
                        "bases": bases_text,
                        "line": node.start_point[0] + 1,
                        "file": inp.path,
                    })
            for child in node.children:
                walk(child)

        walk(root)
        return ToolOutput(success=True, data={"models": models, "count": len(models)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
