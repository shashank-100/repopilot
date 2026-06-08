"""CLI entry point for the evaluation framework.

Usage:
    uv run python -m repopilot.evaluation.run --repo /path/to/repo
    uv run python -m repopilot.evaluation.run --repo /path/to/repo --tasks fix_bug add_endpoint
    uv run python -m repopilot.evaluation.run --repo /path/to/repo --parallel
    uv run python -m repopilot.evaluation.run --repo /path/to/repo --output report.json

Also callable as: make eval REPO=/path/to/repo
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from repopilot.observability import configure_logging


def _print_report(suite_dict: dict) -> None:
    s = suite_dict["summary"]
    print("\n" + "═" * 62)
    print("  RepoPilot Evaluation Report")
    print("═" * 62)
    print(f"  Tasks          : {s['total_tasks']}")
    print(f"  Success rate   : {s['success_rate']*100:.0f}%")
    print(f"  Avg completion : {s['avg_completion_rate']*100:.0f}%")
    print(f"  Avg time       : {s['avg_execution_time_s']:.1f}s")
    print(f"  Avg tool calls : {s['avg_tool_calls']:.1f}")
    print(f"  Avg repairs    : {s['avg_repair_attempts']:.2f}")
    print("─" * 62)
    for t in suite_dict["tasks"]:
        icon = "✓" if t["success"] else "✗"
        print(f"  {icon} [{t['task_id']}] {t['task_name']}")
        print(f"      phase={t['final_phase']}  time={t['execution_time_s']}s  "
              f"tools={t['tool_call_count']}  repairs={t['repair_attempts']}")
        for c in t["criteria"]:
            mark = "✓" if c["passed"] else "✗"
            print(f"      {mark} {c['label']}")
        if t["error"]:
            print(f"      ⚠ error: {t['error'][:120]}")
    print("═" * 62 + "\n")


def _markdown_report(suite_dict: dict, repo: str) -> str:
    s = suite_dict["summary"]
    lines = [
        "# RepoPilot Benchmark Report",
        "",
        f"Target repository: `{repo}`  ",
        f"Tasks run: **{s['total_tasks']}**",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Success rate | {s['success_rate']*100:.0f}% |",
        f"| Avg completion rate | {s['avg_completion_rate']*100:.0f}% |",
        f"| Avg execution time | {s['avg_execution_time_s']:.1f}s |",
        f"| Avg tool calls | {s['avg_tool_calls']:.1f} |",
        f"| Avg repair attempts | {s['avg_repair_attempts']:.2f} |",
        "",
        "## Per-task results",
        "",
        "| Task | Result | Phase | Time | Tools | Repairs |",
        "|------|--------|-------|------|-------|---------|",
    ]
    for t in suite_dict["tasks"]:
        icon = "✅ pass" if t["success"] else "❌ fail"
        lines.append(
            f"| {t['task_name']} | {icon} | {t['final_phase']} | "
            f"{t['execution_time_s']:.0f}s | {t['tool_call_count']} | {t['repair_attempts']} |"
        )
    lines.append("")
    lines.append("## Criteria detail")
    lines.append("")
    for t in suite_dict["tasks"]:
        lines.append(f"### {t['task_name']}")
        lines.append(f"> {t['objective']}")
        lines.append("")
        for c in t["criteria"]:
            mark = "✅" if c["passed"] else "❌"
            lines.append(f"- {mark} {c['label']}")
        if t.get("error"):
            lines.append(f"- ⚠️ error: {t['error'][:200]}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    configure_logging()

    parser = argparse.ArgumentParser(description="RepoPilot evaluation harness")
    parser.add_argument("--repo", required=True, help="Path to the target repository")
    parser.add_argument("--tasks", nargs="*", help="Task IDs to run (default: all)")
    parser.add_argument("--parallel", action="store_true", help="Run tasks concurrently")
    parser.add_argument("--output", default="", help="Write JSON report to this file")
    parser.add_argument("--markdown", default="", help="Write a markdown report to this file")
    args = parser.parse_args()

    from repopilot.evaluation.tasks import DEFAULT_TASKS
    from repopilot.evaluation.runner import run_suite

    tasks_to_run = DEFAULT_TASKS
    if args.tasks:
        task_map = {t.id: t for t in DEFAULT_TASKS}
        tasks_to_run = [task_map[tid] for tid in args.tasks if tid in task_map]
        missing = [tid for tid in args.tasks if tid not in task_map]
        if missing:
            print(f"Unknown task IDs: {missing}", file=sys.stderr)
            sys.exit(1)

    # Inject repo_path into each task
    for t in tasks_to_run:
        t.repo_path = args.repo

    print(f"Running {len(tasks_to_run)} task(s) against {args.repo} …")
    suite = run_suite(tasks_to_run, args.repo, parallel=args.parallel)
    report = suite.to_dict()

    _print_report(report)

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2))
        print(f"JSON report written to {args.output}")

    if args.markdown:
        Path(args.markdown).write_text(_markdown_report(report, args.repo))
        print(f"Markdown report written to {args.markdown}")

    # Exit 1 if any task failed
    if suite.success_rate < 1.0:
        sys.exit(1)


if __name__ == "__main__":
    main()
