# Architecture — RepoPilot

RepoPilot is an autonomous coding agent. Given a GitHub repo and an objective, it
clones the repo, understands it, plans a change, edits the code, validates, and
opens a pull request. This document explains how the pieces fit together.

---

## 1. System overview

```
┌─────────────────┐      HTTPS       ┌──────────────────────────┐
│  Next.js dashboard│  ───────────►   │   FastAPI backend         │
│  (Vercel)         │   /runs, /repos │   (Railway, Docker)       │
└─────────────────┘                  │                          │
                                     │  ┌────────────────────┐  │
                                     │  │ LangGraph workflow │  │
                                     │  │  (9 agents)        │  │
                                     │  └────────┬───────────┘  │
                                     │           │ tools         │
                                     │  ┌────────▼───────────┐  │
                                     │  │ ToolRegistry (50)  │  │
                                     │  └────────────────────┘  │
                                     └───────┬───────────┬──────┘
                                             │           │
                          ┌──────────────────▼──┐   ┌────▼─────────────┐
                          │ PostgreSQL (Supabase)│   │ GitHub (clone +  │
                          │  run state           │   │  App PRs)        │
                          └──────────────────────┘   └──────────────────┘
                                             │
                                  ┌──────────▼───────────┐
                                  │  Anthropic API        │
                                  │  Haiku + Sonnet       │
                                  └───────────────────────┘
```

**Three deployed surfaces:**
- **Dashboard** (Next.js / Vercel) — launch runs, watch live progress, view the PR.
- **API** (FastAPI / Railway, Dockerized) — REST endpoints + the agent runtime.
- **Database** (Postgres / Supabase) — persists run state across restarts.

---

## 2. The state contract

The entire system is built around one TypedDict: **`RepoPilotState`** (`repopilot/state.py`).
Every agent reads from and writes to this single object — agents never call each
other directly. This makes the graph resumable, inspectable, and persistable.

Key fields: `objective`, `repo_path`, `repository_map`, `architecture_context`,
`repository_graph` (NetworkX, in-memory only), `execution_plan`, `tool_history`,
`modified_files`, `validation_results`, `generated_pr`, `repair_attempts`,
`current_phase`, `token_usage`.

**Why state-as-contract:** it's the single decision that makes everything else
composable — Postgres persistence, the subagent tool returning a state slice, and
the eval harness asserting on fields all fall out of it for free.

---

## 3. The agent pipeline (LangGraph)

`repopilot/graph/workflow.py` wires 9 agent nodes into a `StateGraph`:

```
discovery → knowledge → architecture → planning → implementation
   → validation ─(advisory)→ documentation → pr_generation → END
        └─(real test/lint failure, <3 tries)→ reflection → planning
```

| Agent | File | Role | Model |
|-------|------|------|-------|
| Discovery | `agents/discovery.py` | Map the repo → `RepositoryMap` | Haiku |
| Knowledge | `agents/knowledge.py` | Tree-sitter AST → NetworkX graph | (no LLM) |
| Architecture | `agents/architecture.py` | Consume graph → `ArchitectureContext` | Haiku |
| Planning | `agents/planning.py` | Objective + context → `execution_plan` | **Sonnet** |
| Implementation | `agents/implementation.py` | Execute plan steps, edit files | Haiku |
| Validation | `agents/validation.py` | Advisory tiered checks | (no LLM) |
| Reflection | `agents/reflection.py` | Diagnose failure → plan patches | **Sonnet** |
| Documentation | `agents/documentation.py` | Docstrings + migration notes | Haiku |
| PR Generation | `agents/pr_generation.py` | Compose the PR | **Sonnet** |

**Hybrid model routing** (`repopilot/llm.py`): mechanical agents use Haiku (cheap,
fast); reasoning agents that caused failures under Haiku (planning, reflection, PR)
use Sonnet. Controlled by `default_llm()` / `heavy_llm()`.

### 3a. What each agent does (in detail)

The 9 agents fall into five phases of work:

**Understand the repo (1–3)**
1. **Discovery** — scans directory structure, detects framework + language, finds
   entry points and key files. Writes `repository_map`.
2. **Knowledge** — tree-sitter parses every source file into an AST and builds a
   NetworkX graph of imports → classes → functions → routes. No LLM; pure static
   analysis. Writes `repository_graph` (held in memory only — not JSON-serialisable).
3. **Architecture** — queries the graph to identify API routes, data models,
   services, and external dependencies. Writes `architecture_context`.

**Decide what to do (4)**
4. **Planning** — combines the objective with the repo map + architecture into an
   ordered list of `ExecutionStep`s, each with `files_to_modify`, `tool_hints`, and
   `depends_on`. Writes `execution_plan`. Uses Sonnet because a bad plan is the most
   expensive failure (it causes scope-creep and repair loops).

**Act (5)**
5. **Implementation** — iterates the plan's steps. For each step it reads the
   relevant files (cached so each file is embedded once — `_file_cache`/`_shown`),
   asks the LLM for a structured `_StepResult` (`{summary, edits:[{path,content}]}`),
   and applies each edit via the `fs.write_file` tool. Appends to `modified_files`.
   A failed step is marked `failed` and the loop continues so validation sees the
   whole picture.

**Check & recover (6–7)**
6. **Validation** — advisory, tiered (see §5). Writes `validation_results` with a
   `severity` and `validated_with`. Never blocks.
7. **Reflection** — only runs on a real, fixable test/lint failure. Reads the
   validation findings + failed steps, diagnoses a root cause, and emits
   `plan_patches` that the Planning agent applies on the next pass. Increments
   `repair_attempts` (capped at 3).

**Deliver (8–9)**
8. **Documentation** — for each modified file, generates an updated module docstring
   and a one-line migration note (Haiku, cheap). Stores notes for the PR.
9. **PR Generation** — composes the PR (title, summary, changes, tests-executed,
   risks, rollback) honestly reflecting the validation tier, then `github_pr.py`
   opens a real GitHub PR. Writes `generated_pr` (incl. the PR `url`).

### 3b. The agent contract

Every agent is a class with one method — `run(state) -> state` — taking the LLM
and tool executor at init:

```python
class SomeAgent:
    def run(self, state: RepoPilotState) -> RepoPilotState:
        x = state["..."]                 # 1. READ from shared state
        result = invoke_with_retry(...)  # 2. REASON (LLM, structured output)
        executor.run("fs.write_file",..) # 3. ACT (tools, via ToolExecutor)
        state["..."] = result            # 4. WRITE back to state
        return state
```

Agents **never call each other** — they communicate only through `RepoPilotState`.
LLM responses are forced into Pydantic schemas via `.with_structured_output(...)`,
so an agent gets typed objects, not raw text to parse.

---

## 4. The tool system

`repopilot/tools/base.py` defines a `ToolRegistry` and a `@tool` decorator.
**50 tools** auto-register at import across 5 namespaces:

| Namespace | Count | Examples |
|-----------|-------|----------|
| `fs` | 12 | read/write/append/find/grep/move |
| `git` | 12 | status/diff/commit/branch/checkout |
| `terminal` | 9 | pytest/mypy/ruff/run_command |
| `analysis` | 10 | dep_graph/call_graph/find_routes/find_models |
| `research` | 6 | search_docs/fetch_docs/summarize_file |

Plus `subagent.spawn_subgraph` — spawns a child LangGraph run in an **isolated
`RepoPilotState`** with a scoped `phases` subset and returns a structured
`SubgraphResult`.

**Dispatch is registry lookup, never conditionals.** `ToolExecutor`
(`tools/executor.py`) wraps every call in an OpenTelemetry span and appends to
`tool_history`.

### 4a. How a tool is defined, registered, and called

**1. Defined declaratively** — a Pydantic input schema + a decorated function that
always returns the uniform `ToolOutput{success, data, error}`:

```python
class ReadFileInput(ToolInput):              # typed, validated args
    path: str
    start_line: int | None = None

@tool("fs.read_file", "Read file contents…") # registers on import
def read_file(inp: ReadFileInput) -> ToolOutput:
    ...
    return ToolOutput(success=True, data={"content": content})
```

**2. Auto-registered** — the `@tool` decorator reads the function's first-param
annotation to capture the schema, then calls `registry.register(ToolMeta(...))`.
Writing the file *is* the registration — no manual wiring.

**3. Discovered** — `load_all_tools()` walks each namespace package with
`pkgutil.iter_modules` and imports every module, firing all 50 decorators so the
singleton `registry` is fully populated.

**4. Invoked** — agents call `executor.run("fs.read_file", path="/x.py")`. The
`ToolExecutor` looks the tool up, validates args against the Pydantic schema, opens
an OTel span, runs it, records the call into `state["tool_history"]`, and returns the
`ToolOutput`. Because failures return `success=False` (never raise), agents can chain
tools without special-casing errors.

This uniform `ToolInput`/`ToolOutput` shape is also what enables **composable tool
I/O** — one tool's `data` is a valid input to another, and agents thread these
results through `RepoPilotState`.

---

## 5. Validation (advisory, tiered)

Validation never blocks the run — many repos can't be "validated by running code."
It picks the **strongest available tier** and records severity:

```
has pytest / npm test?  → run tests          ┐
else has mypy/ruff cfg? → static analysis    ├─ severity: pass | warnings | not_validated
else changed files?     → syntax parse        │  validated_with: tests|lint|syntax|none
else                    → not_validated       ┘
```

The repair loop (`_route_after_validation`) engages only for **real test/lint
failures**, capped at 3 attempts, then ships anyway with findings noted in the PR.

---

## 6. GitHub integration

- **Clone** (`api/routers/runs.py::_clone_repo`): a GitHub URL is shallow-cloned to
  a temp dir before the graph runs.
- **Auth** (`github_auth.py`): a **GitHub App** mints a short-lived installation
  access token per repo (Devin-style — anyone can install the app on their repos).
  Falls back to a PAT if configured.
- **PR** (`github_pr.py`): after `pr_generation`, create a branch, commit
  `modified_files`, push with the install token, and open a PR via the REST API.
  Skips gracefully if no credentials or not a GitHub clone.

---

## 7. Persistence

`repopilot/state_store.py` is the seam. With `DATABASE_URL` set it writes through to
Postgres (`db/store.py`, async SQLAlchemy + asyncpg) **and** mirrors in memory;
DB failures degrade gracefully to the in-memory mirror instead of 500ing.
Without `DATABASE_URL` it's pure in-memory.

Supabase note: the direct host is IPv6-only and unreachable from Railway (IPv4), so
the deployment uses the **transaction pooler** (`engine.py` disables asyncpg's
prepared-statement cache for pgbouncer compatibility).

---

## 8. Production scaffolding

| Concern | Where |
|---------|-------|
| Structured logging | `observability/logging.py` (structlog) |
| Tracing | `observability/tracing.py` (OTel) + per-tool spans |
| Retries + backoff | `llm.py::invoke_with_retry` (tenacity, exp backoff) |
| Rate limiting | `llm.py` (AsyncLimiter on LLM) + `api/middleware/rate_limit.py` (slowapi) |
| Typed errors | `errors.py` hierarchy |
| Evaluation | `evaluation/` (5 benchmark tasks + metrics) |
| Tests | `tests/` — 100 passing, unit + integration |

---

## 9. Request lifecycle (a run, end to end)

1. `POST /runs {objective, repo_path}` → creates state, returns `run_id`, schedules a background task.
2. Background task: if `repo_path` is a GitHub URL, **clone** it.
3. `build_graph().invoke(state)` runs the 9-agent pipeline; each agent mutates state, each tool call is traced + recorded.
4. On `pr_generation`, `maybe_open_pr` opens a real GitHub PR.
5. Token usage is computed and stored; state is persisted.
6. Dashboard polls `GET /runs/{id}` every 2.5s and renders the live thread + PR link.
