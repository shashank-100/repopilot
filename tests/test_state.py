import pytest

from repopilot import state_store
from repopilot.state_store import create_run, delete_run, get_run, list_runs, update_run


def test_create_run():
    state = create_run("add rate limiting", "/tmp/repo")
    assert state["objective"] == "add rate limiting"
    assert state["repo_path"] == "/tmp/repo"
    assert state["current_phase"] == "created"
    assert state["repair_attempts"] == 0
    assert state["tool_history"] == []
    delete_run(state["run_id"])


def test_get_run_not_found():
    with pytest.raises(KeyError):
        get_run("nonexistent-run-id")


def test_update_run():
    state = create_run("test", "/tmp/repo")
    run_id = state["run_id"]
    state["current_phase"] = "discovery"
    update_run(state)
    retrieved = get_run(run_id)
    assert retrieved["current_phase"] == "discovery"
    delete_run(run_id)


def test_list_runs():
    s1 = create_run("obj1", "/tmp/r1")
    s2 = create_run("obj2", "/tmp/r2")
    runs = list(list_runs())
    assert s1["run_id"] in runs
    assert s2["run_id"] in runs
    delete_run(s1["run_id"])
    delete_run(s2["run_id"])
