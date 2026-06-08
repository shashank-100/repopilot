"""Run management endpoints."""
from __future__ import annotations

import asyncio
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from repopilot import state_store
from repopilot.api.middleware.rate_limit import limiter
from repopilot.state import RepoPilotState

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/runs", tags=["runs"])

# Matches https://github.com/owner/repo, github.com/owner/repo, owner/repo, *.git
_GITHUB_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/[\w.-]+/[\w.-]+/?$"
    r"|^[\w.-]+/[\w.-]+$"  # bare owner/repo shorthand
    r"|^https?://.+\.git$"
)


class CreateRunRequest(BaseModel):
    objective: str
    repo_path: str


def _is_repo_url(s: str) -> bool:
    return bool(_GITHUB_RE.match(s.strip()))


def _clone_repo(url: str) -> str:
    """Clone a GitHub repo (shallow) to a temp dir and return the local path."""
    raw = url.strip()
    # Normalise shorthand and bare github.com paths to a clone URL
    if raw.startswith("http") and raw.endswith(".git"):
        clone_url = raw
    elif "github.com" in raw:
        clone_url = "https://" + raw.split("https://")[-1].split("http://")[-1]
        clone_url = clone_url.rstrip("/")
        if not clone_url.endswith(".git"):
            clone_url += ".git"
    else:  # owner/repo shorthand
        clone_url = f"https://github.com/{raw}.git"

    dest = tempfile.mkdtemp(prefix="repopilot_clone_")
    logger.info("repo.clone.start", url=clone_url, dest=dest)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", clone_url, dest],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr.strip()[:300]}")
    logger.info("repo.clone.done", dest=dest)
    return dest


def _safe_snapshot(state: RepoPilotState) -> dict[str, Any]:
    return {k: v for k, v in state.items() if k != "repository_graph"}


async def _run_graph(run_id: str) -> None:
    from repopilot.graph.workflow import build_graph
    from repopilot.llm import token_counter
    from repopilot.state_store import get_run, update_run

    state = get_run(run_id)
    tokens_before = token_counter.snapshot()
    try:
        # If the repo_path is a GitHub URL, clone it first and point the run
        # at the local checkout. This is what makes the hosted demo usable —
        # users paste a GitHub URL instead of a path on the server's disk.
        if _is_repo_url(state["repo_path"]):
            state["current_phase"] = "cloning"
            state["observations"].append(f"cloning {state['repo_path']} …")
            update_run(state)
            cloned = await asyncio.to_thread(_clone_repo, state["repo_path"])
            state["repo_path"] = cloned
            state["observations"].append(f"cloned to {cloned}")
            update_run(state)

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
