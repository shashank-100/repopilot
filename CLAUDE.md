# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**RepoPilot** — an autonomous AI coding agent built on LangGraph + LangChain + Anthropic Claude. Given a repository path and an objective (e.g. "add rate limiting middleware"), it discovers the repo structure, builds a knowledge graph, plans the changes, implements them, validates, and generates a PR summary.

## Development Commands

```bash
# Install dependencies
uv sync

# Start API (local dev, hot reload)
make dev          # → uvicorn repopilot.api.main:app --reload --port 8000

# Docker
make up           # docker compose up -d
make down         # docker compose down

# Tests
make test         # pytest tests/ -x --cov=repopilot
pytest tests/test_tools.py::test_fs_write_read -xvs   # single test

# Lint / format
make lint         # ruff check + mypy
make fmt          # ruff format + ruff check --fix

# Evaluation benchmarks (Phase 16, stub for now)
make eval
```

Copy `.env.example` → `.env` and set `ANTHROPIC_API_KEY` before running.

## Architecture

### State (`repopilot/state.py`)
`RepoPilotState` is the single TypedDict that flows through the entire LangGraph graph. All agents read from and write to it. Key fields:
- `objective` / `repo_path` — inputs
- `repository_map` — `RepositoryMap` from the Discovery agent
- `architecture_context` — `ArchitectureContext` from the Architecture agent
- `repository_graph` — `networkx.DiGraph` built by `KnowledgeGraphBuilder` (not JSON-serializable; excluded from API responses)
- `execution_plan` — `{"goal": str, "steps": list[ExecutionStep]}` from the Planning agent
- `tool_history` — every tool call with args, result, timing
- `modified_files`, `validation_results`, `generated_pr`, `reflection_report`

In-memory store: `repopilot/state_store.py` (dict keyed by `run_id`). Postgres deferred.

### LangGraph Workflow (`repopilot/graph/workflow.py`)
`build_graph(phases?)` returns a compiled `StateGraph`. Linear by default, with a conditional retry loop after validation:
```
discovery → knowledge → architecture → planning → implementation
    → validation → (pass) → documentation → pr_generation
               ↘ (fail, attempts < 3) → reflection → planning (replan)
               ↘ (abort) → END
```
`build_graph(phases=["discovery","knowledge"])` is used by the subagent tool to run partial graphs.

### Tool System (`repopilot/tools/`)
- **`base.py`** — `ToolRegistry` singleton, `@tool(name, description)` decorator, `load_all_tools()` (auto-discovers all namespace packages)
- **`executor.py`** — `ToolExecutor`: wraps each call with an OTel span, appends to `state["tool_history"]`
- **`subagent.py`** — `spawn_subgraph` tool: spawns a child LangGraph run in an isolated context, awaits completion, merges results back. Use `spawn_subgraph_async` + `asyncio.gather` for parallel sub-runs.

Tool namespaces and count:
| Namespace | Tools |
|-----------|-------|
| `fs.*` | 12 (read/write/append/delete/find/grep/copy/move/list/mkdir/exists/info) |
| `git.*` | 12 (status/diff/log/show/branch/checkout/commit/add/stash/stash_pop/list_branches/current_branch) |
| `terminal.*` | 9 (pytest/mypy/ruff/ruff_format/build/command/pip_install/python_version/run_script) |
| `analysis.*` | 10 (dep_graph/call_graph/routes/models/classes/functions/imports/framework/lines/complexity) |
| `research.*` | 6 (search_docs/fetch_docs/summarize_file/todos/fixmes/package_info) |

Call via `ToolExecutor.run("fs.read_file", path="...")` or directly: `registry.get("fs.read_file").fn(ReadFileInput(...))`.

### Knowledge Graph (`repopilot/graph/knowledge_graph.py`)
`KnowledgeGraphBuilder.build(repo_path)` walks all `.py` files with tree-sitter, producing a `networkx.DiGraph`. Node types: `file`, `class`, `function`, `route`, `module`. Edge types: `imports`, `defines`, `inherits`, `exposes`. Used by the Architecture agent to find routes/models without re-reading every file.

### Agents (`repopilot/agents/`)
Each agent: `__init__(llm?, executor?)` + `.run(state) -> state`. LLM structured output via `.with_structured_output(PydanticSchema)`. Default LLM: `claude-sonnet-4-6`; cheap subtasks use `claude-haiku-4-5-20251001`.
- **`discovery.py`** → populates `repository_map`
- **`knowledge.py`** → populates `repository_graph`
- **`architecture.py`** → populates `architecture_context`
- **`planning.py`** → populates `execution_plan`; `replan()` patches steps without full re-plan

### API (`repopilot/api/`)
- `GET /health` → `{"status": "ok"}`
- `POST /runs` → creates state, launches graph as a `BackgroundTask`, returns `{"run_id": ...}`
- `GET /runs` → list run IDs
- `GET /runs/{run_id}` → JSON state snapshot (repository_graph excluded)
- `GET /runs/{run_id}/tools` → tool call history

### Observability (`repopilot/observability/`)
- `configure_logging()` — structlog with JSON renderer in prod, console in dev (`REPOPILOT_ENV=development`)
- `configure_tracing()` — OTel `TracerProvider`; sends to OTLP endpoint if `OTEL_EXPORTER_OTLP_ENDPOINT` is set, otherwise silent
- Both called at FastAPI lifespan startup

## Adding New Tools

1. Create `repopilot/tools/<namespace>/my_tool.py`
2. Define `class MyToolInput(ToolInput)` and decorate the function with `@tool("namespace.my_tool", "description")`
3. Import the module in `repopilot/tools/<namespace>/__init__.py`
4. No registration boilerplate needed — `load_all_tools()` picks it up automatically
