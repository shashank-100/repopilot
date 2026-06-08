"""Parallel sub-graph invocation tool.

Spawns a child RepoPilot LangGraph run in an isolated context, awaits completion,
and returns a merged result. Multiple calls can be awaited concurrently by the
planning agent via asyncio.gather — each child run gets its own run_id and is
visible via GET /runs/{run_id}.
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from repopilot.state import RepoPilotState
from repopilot.state_store import create_run, update_run
from repopilot.tools.base import ToolInput, ToolOutput, tool

logger = structlog.get_logger(__name__)


class SpawnSubgraphInput(ToolInput):
    objective: str
    repo_path: str
    # Which phases to run in the child graph: e.g. ["discovery", "knowledge"]
    phases: list[str] = ["discovery", "knowledge", "architecture", "planning"]
    # Optional partial state fields to seed the child run
    seed: dict[str, Any] = {}


class SubgraphResult(ToolOutput):
    child_run_id: str = ""
    execution_plan: dict[str, Any] | None = None
    repository_map: dict[str, Any] | None = None
    modified_files: list[str] = []
    observations: list[str] = []


@tool("subagent.spawn_subgraph", "Spawn a child LangGraph run for a subtask and return its results")
def spawn_subgraph(inp: SpawnSubgraphInput) -> ToolOutput:
    """Synchronous wrapper — runs the async child graph in a new event loop if needed."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside an async context (e.g. FastAPI) — schedule as a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _run_child(inp))
                return future.result()
        else:
            return loop.run_until_complete(_run_child(inp))
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))


async def spawn_subgraph_async(inp: SpawnSubgraphInput) -> SubgraphResult:
    """Async version for use with asyncio.gather in the planning agent."""
    return await _run_child(inp)


async def _run_child(inp: SpawnSubgraphInput) -> SubgraphResult:
    # Import here to avoid circular imports (graph imports tools)
    from repopilot.graph.workflow import build_graph

    child_state = create_run(inp.objective, inp.repo_path)
    child_run_id = child_state["run_id"]

    # Seed with any caller-supplied partial state
    for k, v in inp.seed.items():
        child_state[k] = v  # type: ignore[literal-required]

    logger.info("subagent.start", child_run_id=child_run_id, phases=inp.phases)

    graph = build_graph(phases=inp.phases)
    final_state: RepoPilotState = await asyncio.to_thread(graph.invoke, child_state)

    update_run(final_state)
    logger.info("subagent.complete", child_run_id=child_run_id, phase=final_state.get("current_phase"))

    return SubgraphResult(
        success=True,
        child_run_id=child_run_id,
        execution_plan=final_state.get("execution_plan"),
        repository_map=final_state.get("repository_map"),  # type: ignore[arg-type]
        modified_files=final_state.get("modified_files", []),
        observations=final_state.get("observations", []),
    )
