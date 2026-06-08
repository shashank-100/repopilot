"""Shared pytest fixtures."""
import pytest

from repopilot.tools.base import load_all_tools


@pytest.fixture(autouse=True, scope="session")
def load_all_tools_once():
    """Load all tool namespaces once per test session."""
    load_all_tools()
