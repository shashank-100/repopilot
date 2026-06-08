"""Build a rich knowledge graph of a Python repository using tree-sitter."""
from __future__ import annotations

from pathlib import Path

import networkx as nx

from repopilot.tools.analysis._parser import node_text, parse_file

_SKIP_DIRS = {"__pycache__", ".venv", "venv", ".git", "node_modules", ".mypy_cache"}


class KnowledgeGraphBuilder:
    def build(self, repo_path: str) -> nx.DiGraph:
        G: nx.DiGraph = nx.DiGraph()
        root = Path(repo_path)

        for py_file in root.glob("**/*.py"):
            if any(skip in py_file.parts for skip in _SKIP_DIRS):
                continue
            rel = str(py_file.relative_to(root))
            module_id = rel.replace("/", ".").removesuffix(".py")

            G.add_node(module_id, type="file", file=str(py_file), line=0)

            try:
                file_root, src = parse_file(str(py_file))
            except Exception:
                continue

            self._extract_nodes(G, file_root, src, module_id, str(py_file))

        return G

    def _extract_nodes(
        self,
        G: nx.DiGraph,
        root_node,
        src: bytes,
        module_id: str,
        file_path: str,
    ) -> None:
        def walk(node, parent_class: str | None = None):
            # Imports → edges
            if node.type in ("import_statement", "import_from_statement"):
                text = node_text(node, src)
                parts = text.split()
                if parts[0] == "from" and len(parts) > 1:
                    dep = parts[1].lstrip(".")
                elif parts[0] == "import" and len(parts) > 1:
                    dep = parts[1].split(",")[0].strip()
                else:
                    dep = ""
                if dep:
                    if dep not in G:
                        G.add_node(dep, type="module", file="", line=0)
                    G.add_edge(module_id, dep, type="imports")

            # Class definitions
            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                bases_node = node.child_by_field_name("superclasses")
                name = node_text(name_node, src) if name_node else "<cls>"
                bases_text = node_text(bases_node, src) if bases_node else ""
                class_id = f"{module_id}.{name}"
                G.add_node(class_id, type="class", file=file_path, line=node.start_point[0] + 1, bases=bases_text)
                G.add_edge(module_id, class_id, type="defines")

                # Inheritance edges
                if bases_text:
                    for base in bases_text.strip("()").split(","):
                        base = base.strip()
                        if base:
                            if base not in G:
                                G.add_node(base, type="class", file="", line=0)
                            G.add_edge(class_id, base, type="inherits")

                # Walk class body with parent_class context
                for child in node.children:
                    walk(child, parent_class=class_id)
                return

            # Function / method definitions
            elif node.type in ("function_definition", "async_function_definition"):
                name_node = node.child_by_field_name("name")
                name = node_text(name_node, src) if name_node else "<fn>"
                fn_id = f"{parent_class}.{name}" if parent_class else f"{module_id}.{name}"
                G.add_node(fn_id, type="function", file=file_path, line=node.start_point[0] + 1)
                parent_id = parent_class or module_id
                G.add_edge(parent_id, fn_id, type="defines")

                # Route detection: look for decorators before function
                for child in node.parent.children if node.parent else []:
                    if child.type == "decorator":
                        dec_text = node_text(child, src)
                        if any(m in dec_text for m in [".get(", ".post(", ".put(", ".patch(", ".delete("]):
                            route_id = f"route:{fn_id}"
                            G.add_node(route_id, type="route", file=file_path, line=node.start_point[0] + 1, decorator=dec_text)
                            G.add_edge(fn_id, route_id, type="exposes")

            for child in node.children:
                walk(child, parent_class=parent_class)

        walk(root_node)
