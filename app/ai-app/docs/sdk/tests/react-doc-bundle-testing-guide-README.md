---
title: "React.doc Bundle Testing Guide"
summary: "How to run bundle initialization tests via exec_tools."
tags: ["sdk", "testing", "react.doc", "instructions", "pytest"]
keywords: ["how to test bundles", "bundle validation", "pytest", "react.doc", "exec_tools"]
---

# Bundle Testing Guide

Run initialization tests for any bundle using `exec_tools.execute_code_python`.

## Running tests

Use `exec_tools.execute_code_python` with the following snippet. Replace `openrouter-data` with the target bundle ID:

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

The test file and conftest are at `/opt/app/kdcube_ai_app/apps/chat/sdk/bundle_tests/`. Always run with `cwd="/opt/app"` so pytest picks up the conftest that registers the `--bundle-id` flag.

## Interpreting results

- `5 passed` — bundle initializes correctly
- `5 skipped` — bundle ID not found; check spelling or use the full versioned name (e.g. `openrouter-data@2026-03-11`)
- `FAILED` — initialization error; check the traceback

## Available bundle IDs

- `react.doc`
- `react`
- `openrouter-data`
- `eco`