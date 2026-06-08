"""Shared subprocess helper for terminal tools."""
from __future__ import annotations

import subprocess


def run(
    cmd: list[str],
    cwd: str | None = None,
    timeout: int = 120,
) -> tuple[int, str, str]:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr
