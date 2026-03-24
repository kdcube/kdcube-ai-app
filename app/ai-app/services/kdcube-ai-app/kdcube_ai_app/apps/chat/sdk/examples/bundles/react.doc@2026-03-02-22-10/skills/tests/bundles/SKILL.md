---
name: bundles
id: bundles
description: |
  Guidance for running initialization tests for any bundle via pytest.
  Use this skill when the user asks to test or validate a bundle.
version: 2.0.0
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
  - The agent needs to run bundle initialization tests
author: kdcube
created: 2026-03-20
namespace: tests
---

# Bundle Tests

## How to run tests

Use `exec_tools.execute_code_python` with this snippet. Replace `openrouter-data` with the target bundle ID:

```python
import subprocess
import sys
import os

result = subprocess.run(
    [
        sys.executable, "-m", "pytest",
        "/opt/app/kdcube_ai_app/apps/chat/sdk/bundle_tests/test_initialization.py",
        "--bundle-id=openrouter-data",
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

The test file and conftest live at `/opt/app/kdcube_ai_app/apps/chat/sdk/bundle_tests/`. Always run with `cwd="/opt/app"` so pytest picks up the conftest that registers the `--bundle-id` flag.

## Interpreting results

- `5 passed` — bundle initializes correctly
- `5 skipped` — bundle ID not found; check spelling (e.g. try `openrouter-data@2026-03-11`)
- `FAILED` — initialization error; check the traceback

## Available bundle IDs

- `react.doc`
- `react`
- `openrouter-data`
- `eco`