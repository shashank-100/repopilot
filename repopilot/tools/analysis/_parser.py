"""Shared tree-sitter parser for Python source."""
from __future__ import annotations

from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

PY_LANGUAGE = Language(tspython.language())
_parser: Parser | None = None


def get_parser() -> Parser:
    global _parser
    if _parser is None:
        _parser = Parser(PY_LANGUAGE)
    return _parser


def parse_file(path: str) -> tuple[Node, bytes]:
    src = Path(path).read_bytes()
    tree = get_parser().parse(src)
    return tree.root_node, src


def node_text(node: Node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
