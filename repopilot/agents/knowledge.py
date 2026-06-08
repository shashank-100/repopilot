"""Knowledge Agent — builds the repository knowledge graph via tree-sitter."""
from __future__ import annotations

import structlog

from repopilot.graph.knowledge_graph import KnowledgeGraphBuilder
from repopilot.state import RepoPilotState

logger = structlog.get_logger(__name__)


class KnowledgeAgent:
    def __init__(self) -> None:
        self._builder = KnowledgeGraphBuilder()

    def run(self, state: RepoPilotState) -> RepoPilotState:
        log = logger.bind(run_id=state["run_id"], agent="knowledge")
        log.info("agent.start")

        graph = self._builder.build(state["repo_path"])
        state["repository_graph"] = graph
        state["current_phase"] = "knowledge"

        node_count = graph.number_of_nodes()
        edge_count = graph.number_of_edges()
        state["observations"].append(
            f"Knowledge graph built: {node_count} nodes, {edge_count} edges"
        )
        log.info("agent.done", nodes=node_count, edges=edge_count)
        return state
