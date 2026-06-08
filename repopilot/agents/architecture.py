"""Architecture Analysis Agent — derives ArchitectureContext from the knowledge graph."""
from __future__ import annotations

from typing import Any

import networkx as nx
import structlog
from langchain_core.language_models import BaseChatModel

from repopilot.llm import default_llm, invoke_with_retry
from pydantic import BaseModel, Field

from repopilot.state import RepoPilotState
from repopilot.tools.executor import ToolExecutor

logger = structlog.get_logger(__name__)


class _ArchSchema(BaseModel):
    services: list[dict[str, Any]] = Field(description="Logical service groupings with their files")
    api_routes: list[dict[str, str]] = Field(description="HTTP routes found: method, path, handler, file")
    data_models: list[dict[str, str]] = Field(description="Data model classes: name, type, file")
    external_deps: list[str] = Field(description="External package dependencies")
    test_coverage_estimate: str = Field(description="Rough estimate of test coverage (e.g. 'low / medium / high')")
    summary: str = Field(description="2-3 sentence architecture summary")


class ArchitectureAgent:
    def __init__(self, llm: BaseChatModel | None = None, executor: ToolExecutor | None = None) -> None:
        self._llm = llm or default_llm()
        self._executor = executor

    def run(self, state: RepoPilotState) -> RepoPilotState:
        log = logger.bind(run_id=state["run_id"], agent="architecture")
        log.info("agent.start")

        G: nx.DiGraph | None = state.get("repository_graph")  # type: ignore[assignment]
        repo_map = state.get("repository_map", {})

        # Extract graph summary for the prompt
        graph_summary = self._summarize_graph(G) if G else "Graph not available"

        # Optionally use tool executor to find routes/models directly
        routes_text = ""
        models_text = ""
        if self._executor:
            from repopilot.tools.base import registry
            for tool_meta in registry.list_namespace("analysis"):
                pass  # tools already loaded

        structured_llm = self._llm.with_structured_output(_ArchSchema)
        result: _ArchSchema = invoke_with_retry(
            structured_llm,
            f"Analyze this repository's architecture.\n\n"
            f"Repository map: {repo_map}\n\n"
            f"Knowledge graph summary:\n{graph_summary}\n\n"
            f"Identify services, API routes, data models, and external dependencies."
        )

        state["architecture_context"] = {
            "services": result.services,
            "api_routes": result.api_routes,
            "data_models": result.data_models,
            "external_deps": result.external_deps,
            "test_coverage_estimate": result.test_coverage_estimate,
            "summary": result.summary,
        }
        state["current_phase"] = "architecture"
        state["observations"].append(f"Architecture: {result.summary}")
        log.info("agent.done", routes=len(result.api_routes), models=len(result.data_models))
        return state

    def _summarize_graph(self, G: nx.DiGraph) -> str:
        type_counts: dict[str, int] = {}
        for _, data in G.nodes(data=True):
            t = data.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        route_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "route"]
        model_classes = [n for n, d in G.nodes(data=True) if d.get("type") == "class" and
                         any(b in d.get("bases", "") for b in ["BaseModel", "Base", "DeclarativeBase"])]

        return (
            f"Node type counts: {type_counts}\n"
            f"Route nodes: {route_nodes[:20]}\n"
            f"Model classes: {model_classes[:20]}\n"
            f"Total edges: {G.number_of_edges()}"
        )
