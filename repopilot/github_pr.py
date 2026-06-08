"""Open a real GitHub pull request for a completed run.

After the agent modifies a cloned repo, this module creates a branch, commits
the changes, pushes with an authenticated remote, and opens a PR via the GitHub
REST API using the run's generated_pr content.

Requires GITHUB_TOKEN (a PAT with `repo` scope). If absent, or if the repo
wasn't a GitHub clone, PR creation is skipped gracefully and the generated_pr
summary is kept as-is.
"""
from __future__ import annotations

import os
import re
import subprocess
from typing import Any

import httpx
import structlog

from repopilot.state import RepoPilotState

logger = structlog.get_logger(__name__)

_GH_URL_RE = re.compile(r"github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


def _git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, timeout=120
    )


def _origin_owner_repo(repo_path: str) -> tuple[str, str] | None:
    """Read the origin remote and extract (owner, repo)."""
    res = _git(repo_path, "remote", "get-url", "origin")
    if res.returncode != 0:
        return None
    m = _GH_URL_RE.search(res.stdout.strip())
    if not m:
        return None
    return m.group(1), m.group(2)


def maybe_open_pr(state: RepoPilotState) -> RepoPilotState:
    """Create a GitHub PR if possible; otherwise leave state unchanged."""
    from repopilot.github_auth import get_token

    log = logger.bind(run_id=state["run_id"])
    pr = state.get("generated_pr")
    repo_path = state["repo_path"]
    modified = state.get("modified_files", [])

    if not pr:
        log.info("github_pr.skip", reason="no generated_pr")
        return state
    if not modified:
        log.info("github_pr.skip", reason="no modified files")
        return state

    owner_repo = _origin_owner_repo(repo_path)
    if not owner_repo:
        log.info("github_pr.skip", reason="origin is not a github repo")
        return state
    owner, repo = owner_repo

    # GitHub App installation token (preferred) or PAT fallback.
    token = get_token(owner, repo)
    if not token:
        log.info("github_pr.skip", reason="no GitHub App install or PAT for this repo")
        return state

    try:
        # Determine base branch (default branch of the checkout)
        head_ref = _git(repo_path, "symbolic-ref", "--short", "HEAD")
        base = head_ref.stdout.strip() or "main"

        branch = f"repopilot/{state['run_id'][:8]}"
        _git(repo_path, "checkout", "-b", branch)

        # Configure a committer identity (cloned repos may have none)
        _git(repo_path, "config", "user.email", "repopilot@users.noreply.github.com")
        _git(repo_path, "config", "user.name", "RepoPilot")

        _git(repo_path, "add", "-A")
        commit = _git(repo_path, "commit", "-m", pr.get("title", "RepoPilot changes"))
        if commit.returncode != 0:
            log.warning("github_pr.nothing_to_commit", stderr=commit.stderr[:200])
            return state

        # Authenticated push URL
        auth_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
        push = _git(repo_path, "push", auth_url, f"{branch}:{branch}")
        if push.returncode != 0:
            log.warning("github_pr.push_failed", stderr=push.stderr[:300])
            state["observations"].append(f"PR push failed: {push.stderr.strip()[:120]}")
            return state

        # Open the PR via REST API
        body = _pr_body(pr)
        resp = httpx.post(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={
                "title": pr.get("title", "RepoPilot changes"),
                "head": branch,
                "base": base,
                "body": body,
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            pr_url = resp.json().get("html_url", "")
            pr["url"] = pr_url  # type: ignore[typeddict-unknown-key]
            state["generated_pr"] = pr
            state["observations"].append(f"Opened PR: {pr_url}")
            log.info("github_pr.opened", url=pr_url)
        else:
            log.warning("github_pr.api_failed", status=resp.status_code, body=resp.text[:300])
            state["observations"].append(f"PR API error {resp.status_code}: {resp.text[:120]}")
    except Exception as exc:  # noqa: BLE001
        log.warning("github_pr.error", error=str(exc))
        state["observations"].append(f"PR creation error: {str(exc)[:120]}")

    return state


def _pr_body(pr: dict[str, Any]) -> str:
    lines = [pr.get("summary", ""), ""]
    if pr.get("changes"):
        lines.append("## Changes")
        lines += [f"- {c}" for c in pr["changes"]]
        lines.append("")
    if pr.get("tests_executed"):
        lines.append("## Tests")
        lines += [f"- {t}" for t in pr["tests_executed"]]
        lines.append("")
    if pr.get("risks"):
        lines.append("## Risks")
        lines += [f"- {r}" for r in pr["risks"]]
        lines.append("")
    if pr.get("rollback_plan"):
        lines.append("## Rollback")
        lines.append(pr["rollback_plan"])
    lines.append("")
    lines.append("---\n🤖 Generated by RepoPilot")
    return "\n".join(lines)
