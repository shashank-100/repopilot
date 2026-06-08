"""Run management endpoints."""
from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from repopilot import state_store
from repopilot.api.middleware.rate_limit import limiter
from repopilot.state import RepoPilotState

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    objective: str
    repo_path: str


def _safe_snapshot(state: RepoPilotState) -> dict[str, Any]:
    return {k: v for k, v in state.items() if k != "repository_graph"}


async def _run_graph(run_id: str) -> None:
    from repopilot.graph.workflow import build_graph
    from repopilot.llm import token_counter
    from repopilot.state_store import get_run, update_run

    state = get_run(run_id)
    tokens_before = token_counter.snapshot()
    try:
        graph = build_graph()
        final: RepoPilotState = await asyncio.to_thread(graph.invoke, state)
        # Record token usage for this run
        after = token_counter.snapshot()
        final["token_usage"] = {  # type: ignore[typeddict-unknown-key]
            "input_tokens": after["input_tokens"] - tokens_before["input_tokens"],
            "output_tokens": after["output_tokens"] - tokens_before["output_tokens"],
            "total_tokens": after["total_tokens"] - tokens_before["total_tokens"],
            "llm_calls": after["llm_calls"] - tokens_before["llm_calls"],
        }
        update_run(final)
        logger.info(
            "run.complete",
            run_id=run_id,
            phase=final.get("current_phase"),
            tool_calls=len(final.get("tool_history", [])),
            **final["token_usage"],  # type: ignore[typeddict-item]
        )
    except Exception as exc:
        state["error"] = str(exc)
        state["current_phase"] = "error"
        update_run(state)
        logger.error("run.failed", run_id=run_id, error=str(exc))


@router.post("", status_code=202)
@limiter.limit("10/minute")
async def create_run(
    request: Request, body: CreateRunRequest, background_tasks: BackgroundTasks
) -> dict[str, str]:
    state = state_store.create_run(body.objective, body.repo_path)
    run_id = state["run_id"]
    background_tasks.add_task(_run_graph, run_id)
    logger.info("run.created", run_id=run_id)
    return {"run_id": run_id}


@router.get("")
@limiter.limit("60/minute")
async def list_runs(request: Request) -> dict[str, list[str]]:
    return {"run_ids": list(state_store.list_runs())}


@router.get("/{run_id}")
@limiter.limit("60/minute")
async def get_run(request: Request, run_id: str) -> dict[str, Any]:
    try:
        state = state_store.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    return _safe_snapshot(state)


@router.get("/{run_id}/tools")
@limiter.limit("60/minute")
async def get_tool_history(request: Request, run_id: str) -> dict[str, Any]:
    try:
        state = state_store.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    return {"run_id": run_id, "tool_history": state["tool_history"]}
