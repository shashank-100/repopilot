"""Shared helper for running git commands."""
from __future__ import annotations

import subprocess


def git(repo_path: str, *args: str, check: bool = True) -> tuple[int, str, str]:
    result = subprocess.run(
        ["git", "-C", repo_path, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.returncode, result.stdout, result.stderr
