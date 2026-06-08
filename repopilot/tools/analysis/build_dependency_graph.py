"""Build a module-level import dependency graph for a repo."""
from pathlib import Path

import networkx as nx

from repopilot.tools.analysis._parser import node_text, parse_file
from repopilot.tools.base import ToolInput, ToolOutput, tool


class BuildDependencyGraphInput(ToolInput):
    repo_path: str
    as_adjacency: bool = True


@tool("analysis.build_dependency_graph", "Build a module import dependency graph for a Python repo")
def build_dependency_graph(inp: BuildDependencyGraphInput) -> ToolOutput:
    try:
        root = Path(inp.repo_path)
        G: nx.DiGraph = nx.DiGraph()

        for py_file in root.glob("**/*.py"):
            if any(p in str(py_file) for p in ["__pycache__", ".venv", "venv"]):
                continue
            module = str(py_file.relative_to(root)).replace("/", ".").removesuffix(".py")
            G.add_node(module, type="module", file=str(py_file))
            try:
                file_root, src = parse_file(str(py_file))
            except Exception:
                continue

            def walk(node):
                if node.type in ("import_statement", "import_from_statement"):
                    text = node_text(node, src)
                    # Extract the top-level module name
                    parts = text.split()
                    if parts[0] == "from" and len(parts) > 1:
                        dep = parts[1].lstrip(".")
                    elif parts[0] == "import" and len(parts) > 1:
                        dep = parts[1].split(",")[0].strip()
                    else:
                        dep = ""
                    if dep:
                        G.add_node(dep, type="module")
                        G.add_edge(module, dep, type="imports")
                for child in node.children:
                    walk(child)

            walk(file_root)

        if inp.as_adjacency:
            adj = {n: list(G.successors(n)) for n in G.nodes}
            return ToolOutput(success=True, data={"adjacency": adj, "node_count": G.number_of_nodes(), "edge_count": G.number_of_edges()})
        return ToolOutput(success=True, data={"nodes": list(G.nodes), "edges": list(G.edges)})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
