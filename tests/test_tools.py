import tempfile
from pathlib import Path

import pytest

from repopilot.tools.base import registry


def test_registry_has_core_tools():
    """Verify the core non-analysis tools are registered (40 minimum)."""
    names = registry.names()
    assert len(names) >= 40, f"Expected ≥40 core tools, got {len(names)}: {names}"
    # Check key tools from each namespace are present
    assert "fs.read_file" in names
    assert "git.git_status" in names
    assert "terminal.run_pytest" in names
    assert "research.find_todos" in names
    assert "subagent.spawn_subgraph" in names


def test_fs_write_read(tmp_path):
    p = tmp_path / "hello.txt"
    meta = registry.get("fs.write_file")
    result = meta.fn(meta.input_schema(path=str(p), content="hello world"))
    assert result.success

    meta2 = registry.get("fs.read_file")
    result2 = meta2.fn(meta2.input_schema(path=str(p)))
    assert result2.success
    assert "hello world" in result2.data["content"]


def test_fs_find_files(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "b.py").write_text("y = 2")
    meta = registry.get("fs.find_files")
    result = meta.fn(meta.input_schema(root=str(tmp_path), pattern="**/*.py"))
    assert result.success
    assert result.data["count"] == 2


def test_fs_grep(tmp_path):
    (tmp_path / "src.py").write_text("def hello(): pass\n# TODO: fix this\n")
    meta = registry.get("fs.grep_files")
    result = meta.fn(meta.input_schema(root=str(tmp_path), pattern="TODO"))
    assert result.success
    assert len(result.data["matches"]) == 1


requires_analysis = pytest.mark.skipif(
    "analysis.detect_framework" not in registry.names(),
    reason="analysis tools not available (tree-sitter-python not installed in this env)"
)


@requires_analysis
def test_analysis_detect_framework(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n')
    meta = registry.get("analysis.detect_framework")
    result = meta.fn(meta.input_schema(repo_path=str(tmp_path)))
    assert result.success
    assert "fastapi" in result.data["frameworks"]


@requires_analysis
def test_analysis_find_functions(tmp_path):
    py = tmp_path / "code.py"
    py.write_text("def foo(): pass\nasync def bar(): pass\n")
    meta = registry.get("analysis.find_functions")
    result = meta.fn(meta.input_schema(path=str(py)))
    assert result.success
    names = [f["name"] for f in result.data["functions"]]
    assert "foo" in names
    assert "bar" in names


@requires_analysis
def test_analysis_find_classes(tmp_path):
    py = tmp_path / "models.py"
    py.write_text("class Foo(BaseModel): pass\nclass Bar: pass\n")
    meta = registry.get("analysis.find_classes")
    result = meta.fn(meta.input_schema(path=str(py)))
    assert result.success
    assert result.data["count"] == 2


def test_research_find_todos(tmp_path):
    (tmp_path / "main.py").write_text("# TODO: refactor this\nx = 1\n")
    meta = registry.get("research.find_todos")
    result = meta.fn(meta.input_schema(repo_path=str(tmp_path)))
    assert result.success
    assert len(result.data["todos"]) == 1


def test_git_get_current_branch(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    # Need at least one commit for rev-parse HEAD to work
    (tmp_path / "README.md").write_text("hello")
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    meta = registry.get("git.get_current_branch")
    result = meta.fn(meta.input_schema(repo_path=str(tmp_path)))
    assert result.success
    assert result.data["branch"] == "main"
