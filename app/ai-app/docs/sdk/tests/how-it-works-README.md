---
title: "How Bundle Tests Work"
summary: "Overview of the bundle testing system — what it is, how tests are structured, and how they run."
tags: ["sdk", "testing", "overview"]
keywords: ["bundle tests", "how it works", "pytest", "conftest", "--bundle-id"]
see_also:
  - ks:docs/sdk/tests/bundle-tests-README.md
  - ks:docs/sdk/tests/bundle-testing-system-README.md
---

# How Bundle Tests Work

## The idea

One set of pytest tests works for **any bundle**. You pass `--bundle-id=<name>` and the tests load that bundle, initialize it with mock dependencies, and verify it behaves correctly.

```
pytest bundle_tests/ --bundle-id=react.doc     → tests react.doc
pytest bundle_tests/ --bundle-id=openrouter-data → tests openrouter-data
```

Same tests, different bundle — no need to write separate tests per bundle.

## How a test loads a bundle

`conftest.py` provides a `bundle` fixture that:
1. Finds the bundle directory under `sdk/examples/bundles/` by ID
2. Loads the class decorated with `@agentic_workflow` from `entrypoint.py`
3. Instantiates it with a real `Config()` and mock `redis` / `comm_context`

No Redis, no database, no network — tests run fully locally.

## What's tested

Tests are grouped into categories, each in its own file:

- **Initialization** — bundle starts, graph compiles, config loads
- **Configuration** — role_models, bundle_prop(), Redis overrides
- **Graph** — LangGraph nodes, edges, no orphans
- **BundleState** — required fields, no state leakage between requests
- **Error handling** — exceptions caught, error events emitted
- **Event streaming** — SSE event sequence and content
- **Accounting** — token tracking, EconomicsLimitException
- **Model routing** — default model, config/Redis overrides
- **Custom tools** — registration, execution, storage integration
- **Custom skills** — SKILL.md validity, visibility, instruction injection
- **Storage** — S3, Local FS, Redis cache (paths, isolation, fallbacks)

Full list with file names: `ks:docs/sdk/tests/bundle-tests-README.md`

## Where the tests live

```
kdcube_ai_app/apps/chat/sdk/bundle_tests/
  conftest.py       ← bundle fixture + --bundle-id option
  test_*.py         ← one file per category
```

## Skipped vs failed

If the bundle ID is not found, tests are **skipped** — not failed. This is intentional: it means "this bundle doesn't have this feature" or "wrong ID", not a bug. Only `FAILED` means something is broken.