---
title: "How Bundle Tests Work"
summary: "One test suite validates any bundle. No database, no Redis, no API keys needed."
tags: ["sdk", "testing", "overview"]
keywords: ["bundle tests", "how it works", "pytest", "conftest", "--bundle-id"]
see_also:
  - ks:docs/sdk/tests/bundle-testing-system-README.md
  - ks:docs/sdk/tests/bundle-tests-README.md
---

# How Bundle Tests Work

## The core idea

There is one shared test suite that works for **any bundle**. You tell it which bundle to test via `--bundle-id` and it loads, initializes, and validates that bundle automatically.

```
pytest bundle_tests/ --bundle-id=react.doc       → tests react.doc
pytest bundle_tests/ --bundle-id=eco             → tests eco
pytest bundle_tests/ --bundle-id=openrouter-data → tests openrouter-data
```

You don't write separate tests per bundle — the same 244 tests run against any bundle you point them at.

## What happens when a test runs

The `bundle` fixture in `conftest.py` does three things:

1. **Finds** the bundle directory in `sdk/examples/bundles/` by matching the ID
   (e.g. `react.doc` matches `react.doc@2026-03-02-22-10`)
2. **Loads** the class decorated with `@agentic_workflow` from `entrypoint.py`
3. **Initializes** it with a real `Config()`, mocked `redis` and `comm_context`

After that, tests work with a fully initialized bundle instance — real code, real LangGraph, real configuration — just without any network or infrastructure.

## What is mocked

| Mocked | Why |
|---|---|
| `redis` | No Redis server needed in tests |
| `comm_context` | No SSE/WebSocket connection needed |
| `pg_pool = None` | No database needed |
| LLM API | Never called — tests don't invoke actual models |

Everything else is real: the bundle class, its configuration, the LangGraph it builds, skills and tools descriptors, SKILL.md files.

## SKIPPED vs FAILED

- **SKIPPED** — the bundle doesn't have a feature (e.g. no `skills/` directory → skills tests skip). Not a problem.
- **FAILED** — something is actually broken. Needs to be fixed.

A healthy bundle produces only `passed` and `skipped`. Zero `failed`.