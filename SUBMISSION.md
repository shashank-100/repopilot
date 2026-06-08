# Submission — RepoPilot

A Devin-style autonomous coding agent: paste a GitHub URL + an objective, and it
clones the repo, plans, implements changes across multiple files, validates,
and **opens a real pull request**.

## Links

- **Repository:** https://github.com/shashank-100/repopilot
- **Live API:** https://repopilot-api-production.up.railway.app
- **Live dashboard:** https://dashboard-ten-zeta-81.vercel.app
- **Example auto-generated PRs:**
  - https://github.com/shashank-100/CrowdDJ/pull/1 (6 files: validation, error handling, health check)
  - https://github.com/shashank-100/shashank-100/pull/1

## Requirement → implementation map

| # | Requirement | Files / classes |
|---|-------------|-----------------|
| 1 | **50+ tools across 4+ namespaces, registry-driven** | `repopilot/tools/base.py` — `ToolRegistry`, `@tool`, `load_all_tools` (lookup-based dispatch, no conditionals). 50 tools in `repopilot/tools/{fs,git,terminal,analysis,research}/` |
| 2 | **Subagent orchestration (isolated context, scoped tools, structured result)** | `repopilot/tools/subagent.py` — `spawn_subgraph` / `spawn_subgraph_async`: child `RepoPilotState`, `phases` subset, returns `SubgraphResult` |
| 3 | **Long-horizon execution + explicit context management** | `repopilot/agents/implementation.py` — `_file_cache`/`_shown` embed each file once; `repopilot/graph/workflow.py` — validation→reflection→replan loop (`MAX_REPAIR_ATTEMPTS`); `PlanningAgent.replan`, `ExecutionStep.depends_on`. Proven: 18 tool calls / 6 files in one run |
| 4 | **Production scaffolding** | Observability: `repopilot/observability/{logging,tracing}.py` + per-tool OTel spans in `tools/executor.py`. Retries + exponential backoff: `repopilot/llm.py` — `invoke_with_retry` (tenacity `wait_exponential`). Rate limiting: `repopilot/llm.py` (`AsyncLimiter` on LLM calls) + `api/middleware/rate_limit.py` (slowapi on HTTP). Typed errors: `repopilot/errors.py` (used in executor, store, llm). Eval harness: `repopilot/evaluation/`. Tests: `tests/` (92 passing, unit + integration) |
| 5 | **Composable tool I/O** | `repopilot/agents/architecture.py` consumes the Knowledge agent's NetworkX graph + Discovery's `RepositoryMap`; Planning consumes `ArchitectureContext`; Implementation consumes `execution_plan`. State threads in `repopilot/state.py` |

## Beyond the brief

- **GitHub-native:** clone-from-URL (`api/routers/runs.py::_clone_repo`) + auto-PR via
  GitHub App installation token (`github_auth.py`, `github_pr.py`).
- **Deployed:** Railway (API) + Vercel (dashboard) + Supabase (Postgres, via IPv4 pooler).
- **Hybrid model routing:** Haiku for mechanical agents, Sonnet for reasoning
  (planning/PR/reflection) — `repopilot/llm.py`.

## Deliverables in this repo

- `MEMO.md` — one-pager (what built / cut / more time / a defended design decision)
- `benchmark_report.md` — eval harness output (100% on the sampled tasks)
- `submission/session-trace.jsonl` — full Claude Code session trace (native export)
- Video walkthrough — *(link to be added)*

## Run the eval

```bash
make eval REPO=/path/to/repo
# or: uv run python -m repopilot.evaluation.run --repo <path> --markdown benchmark_report.md
```

## Tests

```bash
uv run pytest tests/ -q   # 92 passed, 3 skipped
```
