"""Evaluation runner — executes tasks and collects TaskMetrics.

Each task gets a fresh temporary git repo cloned from the target repo_path,
runs the RepoPilot graph against it, evaluates success criteria, and returns
structured metrics. Tasks are run sequentially by default; pass
parallel=True to run concurrently via asyncio.gather.
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import time
from pathlib import Path

import structlog

from repopilot.evaluation.metrics import SuiteMetrics, TaskMetrics
from repopilot.evaluation.tasks import EvalTask
from repopilot.state import RepoPilotState
from repopilot.state_store import create_run, update_run

logger = structlog.get_logger(__name__)


async def _run_task(task: EvalTask, repo_path: str) -> TaskMetrics:
    """Run one EvalTask against repo_path and return metrics."""
    log = logger.bind(task=task.id)
    log.info("eval.task.start", objective=task.objective)

    # Work in a temp copy so each task is isolated
    tmp_dir = tempfile.mkdtemp(prefix=f"repopilot_eval_{task.id}_")
    try:
        # Copy repo into temp dir (shallow)
        target = Path(tmp_dir) / "repo"
        shutil.copytree(repo_path, str(target), dirs_exist_ok=False,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv"))

        state = create_run(task.objective, str(target))
        run_id = state["run_id"]

        start = time.monotonic()
        error: str | None = None

        try:
            from repopilot.graph.workflow import build_graph
            graph = build_graph()
            final: RepoPilotState = await asyncio.to_thread(graph.invoke, state)
            update_run(final)
        except Exception as exc:
            error = str(exc)
            state["current_phase"] = "error"
            state["error"] = error
            final = state

        elapsed = time.monotonic() - start

        # Evaluate criteria
        criteria_results = [fn(final) for fn in task.success_criteria]
        all_passed = all(criteria_results) and not error

        pr = final.get("generated_pr")
        metrics = TaskMetrics(
            task_id=task.id,
            task_name=task.name,
            objective=task.objective,
            success=all_passed,
            criteria_results=criteria_results,
            criteria_labels=task.criteria_labels,
            execution_time_s=elapsed,
            tool_call_count=len(final.get("tool_history", [])),
            repair_attempts=final.get("repair_attempts", 0),
            final_phase=final.get("current_phase", "unknown"),
            pr_title=pr.get("title") if pr else None,
            modified_files=list(final.get("modified_files", [])),
            error=error or final.get("error"),
        )

        log.info(
            "eval.task.done",
            success=all_passed,
            elapsed_s=round(elapsed, 1),
            tools=metrics.tool_call_count,
        )
        return metrics

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def run_suite_async(
    tasks: list[EvalTask],
    repo_path: str,
    parallel: bool = False,
) -> SuiteMetrics:
    if parallel:
        results = await asyncio.gather(
            *[_run_task(t, repo_path) for t in tasks],
            return_exceptions=False,
        )
        task_metrics = list(results)
    else:
        task_metrics = []
        for task in tasks:
            m = await _run_task(task, repo_path)
            task_metrics.append(m)

    return SuiteMetrics(tasks=task_metrics)


def run_suite(
    tasks: list[EvalTask],
    repo_path: str,
    parallel: bool = False,
) -> SuiteMetrics:
    return asyncio.run(run_suite_async(tasks, repo_path, parallel=parallel))
