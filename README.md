# RepoPilot

> An autonomous coding agent — give it a GitHub repo and an objective, and it
> clones the repo, plans the change, edits the code across multiple files,
> validates, and **opens a real pull request**.

Built on **LangGraph + LangChain + Claude**, behind a FastAPI backend with a
Next.js dashboard. A 9-agent pipeline, 50 registry-driven tools, and Devin-style
GitHub PR creation.

**Live demo**
- Dashboard → https://dashboard-ten-zeta-81.vercel.app
- API → https://repopilot-api-production.up.railway.app

---

## What it does

```
You: "add a /health endpoint with tests"  +  github.com/owner/repo
          │
          ▼
RepoPilot clones the repo → understands it → plans → edits files →
validates → writes docs → opens a pull request
          │
          ▼
A real PR appears on GitHub.
```

Example PRs it opened autonomously:
- [`shashank-100/CrowdDJ#1`](https://github.com/shashank-100/CrowdDJ/pull/1) — 6 files: validation, error handling, health check

---

## How it works (in one diagram)

```
discovery → knowledge → architecture → planning → implementation
   → validation ─(advisory)→ documentation → pr_generation → PR
        └─(real failure, <3 tries)→ reflection → planning
```

Nine agents communicate through a single shared `RepoPilotState`; they never call
each other directly. Tools (read/write files, git, run tests, static analysis) are
the "hands"; agents are the "brains". See **[ARCHITECTURE.md](ARCHITECTURE.md)** for
the full design.

---

## Highlights

- **50 tools across 5 namespaces** (`fs`, `git`, `terminal`, `analysis`, `research`),
  registry-driven dispatch — the model selects tools, no hand-coded conditionals.
- **Subagent orchestration** — a tool spawns an isolated child LangGraph run and
  returns a structured result.
- **Advisory, tiered validation** — runs tests if present, else lint, else
  syntax-check; never blocks the run on repos that can't be "run".
- **Real GitHub PRs** via a GitHub App installation token (anyone can install it).
- **Hybrid model routing** — Haiku for mechanical agents, Sonnet for reasoning.
- **Production scaffolding** — structlog + OpenTelemetry, tenacity retries with
  exponential backoff, rate limiting, typed errors, an eval harness, 100 tests.
- **Persistence** — PostgreSQL (Supabase) with transparent in-memory fallback.

---

## Quick start

### Prerequisites
- Python 3.12, [uv](https://github.com/astral-sh/uv), Node 18+
- An `ANTHROPIC_API_KEY`

### 1. Backend
```bash
cp .env.example .env.local        # add ANTHROPIC_API_KEY
make dev                          # → http://localhost:8000
```

### 2. Dashboard
```bash
cd dashboard
npm install
npm run dev                       # → http://localhost:3000
```

### 3. Launch a run
Open the dashboard → **+ New Run** → pick a GitHub repo + an objective → **Launch**.

Or via the API:
```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"objective": "add a /ping endpoint", "repo_path": "https://github.com/owner/repo"}'
```

---

## Commands

```bash
make dev          # run the API (hot reload)
make test         # run the test suite (100 tests)
make lint         # ruff + mypy
make eval REPO=/path/to/repo      # run the evaluation harness
make up            # docker compose (API + Postgres)
```

---

## Configuration

| Variable | Purpose | Required |
|----------|---------|----------|
| `ANTHROPIC_API_KEY` | LLM calls | **yes** |
| `DATABASE_URL` | Postgres persistence (else in-memory) | no |
| `GITHUB_APP_ID` + `GITHUB_PRIVATE_KEY` | open real PRs (GitHub App) | no |
| `GITHUB_TOKEN` | PR fallback (PAT) | no |
| `REPOPILOT_MODEL` / `REPOPILOT_HEAVY_MODEL` | override model routing | no |

---

## Project layout

```
repopilot/
├── agents/        # 9 agents: discovery → … → pr_generation
├── graph/         # LangGraph workflow + tree-sitter knowledge graph
├── tools/         # 50 tools across fs/git/terminal/analysis/research + subagent
├── api/           # FastAPI app, routers, rate-limit middleware
├── db/            # SQLAlchemy async store (Postgres)
├── evaluation/    # benchmark tasks + metrics harness
├── observability/ # structlog + OpenTelemetry
├── github_auth.py # GitHub App installation tokens
├── github_pr.py   # branch → commit → push → open PR
├── llm.py         # model routing + retries + token tracking
├── errors.py      # typed exception hierarchy
└── state.py       # RepoPilotState — the shared contract
dashboard/         # Next.js + TypeScript dashboard
tests/             # 100 unit + integration tests
```

---

## Docs

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — system design, agent pipeline, data flow
- **[MEMO.md](MEMO.md)** — what was built / cut / a defended design decision
- **[benchmark_report.md](benchmark_report.md)** — evaluation results
- **[SUBMISSION.md](SUBMISSION.md)** — requirement → file map
