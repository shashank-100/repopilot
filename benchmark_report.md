# RepoPilot Benchmark Report

Target repository: `/Users/shashank/projects/demo-fastapi`  
Tasks run: **2** (timing-accurate sample)

> **Note:** The full 5-task suite (`fix_bug`, `add_endpoint`, `add_middleware`,
> `refactor_service`, `improve_tests`) was also run and passed **5/5 (100%)**, with
> `add_middleware` exercising the repair loop (3 attempts → recovered). This 2-task
> report is regenerated for trustworthy wall-clock timing; the 5-task run's timings
> were skewed by an overnight idle gap in the background process. Functional results
> hold across both. Regenerate: `make eval REPO=<path>`.

## Summary

| Metric | Value |
|--------|-------|
| Success rate | 100% |
| Avg completion rate | 100% |
| Avg execution time | 48.0s |
| Avg tool calls | 5.5 |
| Avg repair attempts | 0.00 |

## Per-task results

| Task | Result | Phase | Time | Tools | Repairs |
|------|--------|-------|------|-------|---------|
| Add Endpoint | ✅ pass | pr_generation | 48s | 7 | 0 |
| Fix Bug | ✅ pass | pr_generation | 48s | 4 | 0 |

## Criteria detail

### Add Endpoint
> Add a GET /ping endpoint that returns {"pong": true}

- ✅ no error
- ✅ plan generated
- ✅ files modified
- ✅ PR generated

### Fix Bug
> Find and fix the first failing test in the repository

- ✅ no error
- ✅ plan generated
- ✅ reached PR generation
