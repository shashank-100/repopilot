"""Tests for GitHub PR auto-creation + auth resolution."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from repopilot.github_auth import get_token
from repopilot.github_pr import _origin_owner_repo, maybe_open_pr
from repopilot.state_store import create_run, delete_run


# ── auth resolution ─────────────────────────────────────────────────────────────

def test_get_token_none_without_creds(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_PRIVATE_KEY", raising=False)
    assert get_token("octocat", "Hello-World") is None


def test_get_token_falls_back_to_pat(monkeypatch):
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testpat")
    assert get_token("octocat", "Hello-World") == "ghp_testpat"


# ── origin parsing ──────────────────────────────────────────────────────────────

def test_origin_owner_repo(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin",
         "https://github.com/myorg/myrepo.git"],
        check=True, capture_output=True,
    )
    assert _origin_owner_repo(str(repo)) == ("myorg", "myrepo")


def test_origin_none_for_non_github(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    assert _origin_owner_repo(str(repo)) is None


# ── maybe_open_pr skip paths ────────────────────────────────────────────────────

def test_skip_when_no_generated_pr(tmp_path):
    state = create_run("obj", str(tmp_path))
    state["modified_files"] = ["/x.py"]
    result = maybe_open_pr(state)
    assert "generated_pr" not in result or not result.get("generated_pr")
    delete_run(state["run_id"])


def test_skip_when_no_modified_files(tmp_path):
    state = create_run("obj", str(tmp_path))
    state["generated_pr"] = {  # type: ignore[typeddict-unknown-key]
        "title": "t", "summary": "s", "changes": [],
        "tests_executed": [], "risks": [], "rollback_plan": "",
    }
    result = maybe_open_pr(state)
    # no PR url added
    assert "url" not in result.get("generated_pr", {})
    delete_run(state["run_id"])


def test_skip_when_not_github_repo(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    state = create_run("obj", str(repo))
    state["modified_files"] = [str(repo / "x.py")]
    state["generated_pr"] = {  # type: ignore[typeddict-unknown-key]
        "title": "t", "summary": "s", "changes": ["c"],
        "tests_executed": [], "risks": [], "rollback_plan": "",
    }
    result = maybe_open_pr(state)
    assert "url" not in result.get("generated_pr", {})
    delete_run(state["run_id"])
