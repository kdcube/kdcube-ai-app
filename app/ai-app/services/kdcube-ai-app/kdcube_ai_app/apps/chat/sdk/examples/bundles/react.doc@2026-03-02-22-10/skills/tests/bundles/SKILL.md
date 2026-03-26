---
name: bundles
id: bundles
description: |
  Guidance for running bundle tests via pytest.
  Use this skill when the user asks to test or validate a bundle.
version: 3.0.0
category: testing
tags:
  - bundles
  - pytest
  - validation
  - exec
  - react-doc
when_to_use:
  - The user asks to test a bundle
  - The user asks to validate a bundle works correctly
  - The user asks to run bundle tests
author: kdcube
created: 2026-03-20
namespace: tests
---

# Bundle Tests

## How to run all tests

Use `exec_tools.execute_code_python`. Replace `react.doc` with the target bundle ID:

```python
import subprocess
import sys
import os

bundle_id = "react.doc"  # change to target bundle ID

result = subprocess.run(
    [
        sys.executable, "-m", "pytest",
        "/opt/app/kdcube_ai_app/apps/chat/sdk/bundle_tests/",
        f"--bundle-id={bundle_id}",
        "-v", "--tb=short"
    ],
    capture_output=True,
    text=True,
    cwd="/opt/app"
)

output = result.stdout + result.stderr
print(output)

with open(os.path.join(OUTPUT_DIR, "test_results.txt"), "w") as f:
    f.write(output)
```

Always use `cwd="/opt/app"` so pytest picks up `conftest.py` and the `--bundle-id` flag.

## Quick smoke check (initialization only)

```python
import subprocess, sys, os

bundle_id = "react.doc"

result = subprocess.run(
    [sys.executable, "-m", "pytest",
     "/opt/app/kdcube_ai_app/apps/chat/sdk/bundle_tests/test_initialization.py",
     f"--bundle-id={bundle_id}",
     "-v", "--tb=short"],
    capture_output=True, text=True,
    cwd="/opt/app"
)
print(result.stdout + result.stderr)
```

## Available bundle IDs

- `react.doc`
- `react`
- `react.mcp`
- `openrouter-data`
- `eco`

## What the tests cover

| Category | File(s) |
|---|---|
| Initialization | `test_initialization.py` |
| Configuration | `test_configuration.py` |
| LangGraph structure | `test_graph.py` |
| BundleState fields | `test_bundle_state.py` |
| Error handling | `test_error_handling.py` |
| Event streaming | `test_event_streaming.py` |
| Token accounting | `test_accounting.py` |
| Storage paths | `test_storage.py` |
| Model routing | `test_model_routing.py` |
| Sequential requests | `test_execution_flow.py` |
| Custom tools | `test_custom_tools_*.py` |
| Custom skills | `test_custom_skills_*.py` |
| Cloud storage (S3) | `test_storage_cloud.py` |
| Local FS storage | `test_storage_local_fs.py` |
| Redis cache | `test_storage_redis.py` |
| Storage integration | `test_storage_integration.py` |

## Interpreting results

- `N passed` — tests passed
- `N skipped` — bundle not found (check spelling) or optional feature absent in this bundle — not a failure
- `FAILED` — real problem; check the traceback