import pytest
from fastapi.testclient import TestClient

from repopilot.api.main import app

# raise_server_exceptions=False so background-task errors don't crash the test client
client = TestClient(app, raise_server_exceptions=False)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_runs_empty():
    resp = client.get("/runs")
    assert resp.status_code == 200
    assert "run_ids" in resp.json()


def test_create_run_returns_run_id():
    resp = client.post("/runs", json={"objective": "add tests", "repo_path": "/tmp/repo"})
    assert resp.status_code == 202
    data = resp.json()
    assert "run_id" in data


def test_get_run_not_found():
    resp = client.get("/runs/does-not-exist")
    assert resp.status_code == 404


def test_get_run_after_create():
    resp = client.post("/runs", json={"objective": "add tests", "repo_path": "/tmp/repo"})
    run_id = resp.json()["run_id"]
    resp2 = client.get(f"/runs/{run_id}")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["run_id"] == run_id
    assert data["objective"] == "add tests"


def test_get_tool_history():
    resp = client.post("/runs", json={"objective": "test", "repo_path": "/tmp"})
    run_id = resp.json()["run_id"]
    resp2 = client.get(f"/runs/{run_id}/tools")
    assert resp2.status_code == 200
    assert "tool_history" in resp2.json()
