---
title: "Bundle Testing System"
summary: "How to run pytest bundle tests for any bundle by ID."
tags: ["sdk", "testing", "bundle", "pytest"]
keywords: ["bundle tests", "pytest", "test discovery", "--bundle-id"]
see_also:
  - ks:docs/sdk/tests/bundle-tests-README.md
  - ks:docs/sdk/bundle/bundle-dev-README.md
---

# Bundle Testing System

Tests for bundles live in the SDK codebase and work with any bundle via the `--bundle-id` parameter.

## Test files location

```
kdcube_ai_app/apps/chat/sdk/bundle_tests/
  conftest.py                          ← shared fixtures, --bundle-id option
  test_initialization.py
  test_configuration.py
  test_graph.py
  test_bundle_state.py
  test_error_handling.py
  test_event_streaming.py
  test_accounting.py
  test_storage.py
  test_model_routing.py
  test_execution_flow.py
  test_custom_tools_registration.py
  test_custom_tools_execution.py
  test_custom_tools_storage.py
  test_custom_tools_integration.py
  test_custom_skills_registration.py
  test_custom_skills_manifest.py
  test_custom_skills_visibility.py
  test_custom_skills_execution.py
  test_storage_cloud.py
  test_storage_local_fs.py
  test_storage_redis.py
  test_storage_integration.py
```

## Running tests

Run all tests for a specific bundle:
```bash
cd app/ai-app/services/kdcube-ai-app
pytest kdcube_ai_app/apps/chat/sdk/bundle_tests/ --bundle-id=react.doc -v --tb=short
```

Run a specific category:
```bash
pytest kdcube_ai_app/apps/chat/sdk/bundle_tests/test_initialization.py --bundle-id=react.doc -v
```

Run only storage tests:
```bash
pytest kdcube_ai_app/apps/chat/sdk/bundle_tests/test_storage*.py --bundle-id=react.doc -v
```

## Available bundle IDs

- `react.doc`
- `react`
- `react.mcp`
- `openrouter-data`
- `eco`

If a bundle ID is not found, tests are **skipped** (not failed) with a message listing available bundles.

## How it works

The `conftest.py` registers a `--bundle-id` CLI option. When a test runs, it:
1. Finds the bundle directory under `sdk/examples/bundles/` by ID (supports prefix match, e.g. `openrouter-data` matches `openrouter-data@2026-03-11`)
2. Loads the bundle class from `entrypoint.py`
3. Initializes it with mock `redis` and `comm_context` — no real infrastructure needed

Tests are self-contained and run locally without Redis or a database.

## Running from exec_tools (in-container)

When running inside the container (e.g. via react.doc's `exec_tools.execute_code_python`):

```python
import subprocess, sys, os

result = subprocess.run(
    [sys.executable, "-m", "pytest",
     "/opt/app/kdcube_ai_app/apps/chat/sdk/bundle_tests/",
     "--bundle-id=react.doc",
     "-v", "--tb=short"],
    capture_output=True, text=True,
    cwd="/opt/app"
)
print(result.stdout + result.stderr)
```

Always use `cwd="/opt/app"` so pytest picks up `conftest.py` and the `--bundle-id` flag.