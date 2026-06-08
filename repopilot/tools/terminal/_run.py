"""Shared subprocess helper for terminal tools."""
from __future__ import annotations

import subprocess


def run(
    cmd: list[str],
    cwd: str | None = None,
    timeout: int = 120,
) -> tuple[int, str, str]:
    """Run a command with a hard timeout that KILLS the process group.

    subprocess.run(timeout=...) raises TimeoutExpired but leaves child processes
    (e.g. a hung `pip install`) running, which can wedge the whole agent run.
    We launch in a new process group and kill the whole group on timeout, then
    return a non-zero result instead of propagating the exception.
    """
    import os
    import signal

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,  # new process group → we can kill children too
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        # Kill the entire process group, not just the parent.
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        proc.communicate()  # reap
        return 124, "", f"command timed out after {timeout}s and was killed"
