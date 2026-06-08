# MEMO — RepoPilot

**Domain:** Repository-automation / coding agent. Given a repo path and an objective
("add rate limiting middleware"), RepoPilot discovers the repo, builds a knowledge
graph, plans, implements, validates, reflects/repairs, documents, and generates a PR.

## What I built

A 9-agent LangGraph pipeline behind a FastAPI service, with a Next.js dashboard.

- **50 tools across 5 namespaces** (`fs`, `git`, `terminal`, `analysis`, `research`)
  registered by a decorator, dispatched by registry lookup — never by hand-routed
  conditionals. `repopilot/tools/base.py` (`ToolRegistry`, `@tool`, `load_all_tools`).
- **Subagent orchestration** — `repopilot/tools/subagent.py::spawn_subgraph` launches a
  child LangGraph run with its own isolated `RepoPilotState`, a scoped `phases` subset,
  and returns a structured `SubgraphResult`.
- **Long-horizon execution** — the validation→reflection→replan loop sustains 20–55 tool
  calls per task with plan coherence (`ExecutionStep.depends_on`, `PlanningAgent.replan`).
  Context management is explicit in code: `ImplementationAgent._file_cache` / `_shown`
  embed each file once and reference-by-name thereafter
  (`repopilot/agents/implementation.py`).
- **Production scaffolding** — structlog + OpenTelemetry (`repopilot/observability/`),
  exponential-backoff retries on every LLM call via tenacity
  (`repopilot/llm.py::invoke_with_retry`, wait_exponential 2→30s, 5 attempts),
  an `aiolimiter` rate limit on outbound LLM calls plus slowapi on the HTTP edge
  (`repopilot/api/middleware/rate_limit.py`), a typed error hierarchy
  (`repopilot/errors.py`), an evaluation harness (`repopilot/evaluation/`), and 82
  unit + integration tests.
- **Composable tool I/O** — the agent chain threads structured state: Discovery's
  `RepositoryMap` and Knowledge's NetworkX graph feed Architecture, whose
  `ArchitectureContext` feeds Planning, whose `execution_plan` feeds Implementation.
- **Persistence** — transparent in-memory ↔ PostgreSQL switch on `DATABASE_URL`,
  verified against live Supabase (a run survives a full API restart).

## What I cut

- **Patch-based edits.** Tools rewrite whole files rather than emitting diffs. This is
  the largest remaining token cost; ~20–30% recoverable.
- **Per-agent state persistence.** State is written at graph completion, so the live
  dashboard can't show sub-run progress when backed by Postgres.
- **Dashboard centre panel is demo-seeded** for the empty state; only the live-run path
  is wired to the backend.
- **Knowledge/Architecture run even on trivial repos** — wasted ~5K tokens; a
  complexity gate would skip them for <5-file repos.

## What more time would address

Patch-based editing, a complexity router to skip phases on small repos, parallel eval
execution (`--parallel` exists but the report was generated sequentially), and wiring
the dashboard's live thread as the default view.

## One design decision I'd defend

**Agents communicate only through a single `RepoPilotState` TypedDict — never by calling
each other directly.** A reasonable engineer might wire agents as direct function calls
(simpler, fewer moving parts). I chose state-as-contract because it makes the graph
**resumable and inspectable**: any agent's output is a serializable slice of state, which
is exactly what enabled (a) transparent Postgres persistence with zero agent changes,
(b) the subagent tool returning a structured state slice, and (c) the eval harness
asserting on state fields. Direct calls would have coupled agents to each other's
signatures and made persistence and sub-graph isolation far harder. The cost — a wide
TypedDict and some indirection — is worth the resumability and composability it buys.

## Requirement → implementation map

| Requirement | Where |
|---|---|
| 50+ tools, registry-driven | `repopilot/tools/base.py`, `repopilot/tools/{fs,git,terminal,analysis,research}/` |
| Subagent orchestration | `repopilot/tools/subagent.py` |
| Long-horizon + explicit context mgmt | `repopilot/agents/implementation.py` (`_file_cache`), `graph/workflow.py` (repair loop) |
| Observability | `repopilot/observability/logging.py`, `tracing.py`, `tools/executor.py` (spans) |
| Retries + exponential backoff | `repopilot/llm.py` (`invoke_with_retry`, tenacity `wait_exponential`) |
| Rate limiting (external calls) | `repopilot/llm.py` (`AsyncLimiter`), `api/middleware/rate_limit.py` (slowapi) |
| Typed error handling | `repopilot/errors.py`, used in `tools/executor.py`, `db/store.py`, `llm.py` |
| Evaluation harness | `repopilot/evaluation/{tasks,metrics,runner,run}.py` |
| Unit + integration tests | `tests/` (82 passing) — `test_resilience.py`, `test_state_store_db.py`, `test_evaluation.py` |
| Composable tool I/O | `repopilot/agents/architecture.py` (consumes knowledge graph + repo map) |
| Persistence | `repopilot/db/`, verified on live Supabase |
