
---
title: "Bundle Testing System"
summary: "How to run bundle tests locally and inside the exec container."
tags: ["sdk", "testing", "bundle", "pytest"]
keywords: ["bundle tests", "pytest", "test discovery", "--bundle-id"]
see_also:
  - ks:docs/sdk/tests/how-it-works-README.md
  - ks:docs/sdk/tests/bundle-tests-README.md
  - ks:docs/sdk/bundle/bundle-dev-README.md
---

# Bundle Testing System

Tests live in:
```
kdcube_ai_app/apps/chat/sdk/bundle_tests/
```

## Run locally

```bash
cd app/ai-app/services/kdcube-ai-app

# Full suite
pytest kdcube_ai_app/apps/chat/sdk/bundle_tests/ --bundle-id=react.doc -v

# Quick smoke-check (init + graph only, ~1 sec)
pytest kdcube_ai_app/apps/chat/sdk/bundle_tests/test_initialization.py \
       kdcube_ai_app/apps/chat/sdk/bundle_tests/test_graph.py \
       --bundle-id=react.doc -v

# One category
pytest kdcube_ai_app/apps/chat/sdk/bundle_tests/test_custom_skills_*.py --bundle-id=react.doc -v
```

`react.doc` is the default — you can omit `--bundle-id` when testing it.

## Available bundle IDs

| ID | Description |
|---|---|
| `react.doc` | Documentation reader with knowledge space |
| `react` | Base ReAct bundle |
| `react.mcp` | ReAct + MCP tools |
| `openrouter-data` | Data analysis via OpenRouter |
| `eco` | Custom skills and tools example |

## Run inside the container (via exec_tools)

```python
import subprocess, sys, os

bundle_id = "react.doc"

result = subprocess.run(
    [sys.executable, "-m", "pytest",
     "/opt/app/kdcube_ai_app/apps/chat/sdk/bundle_tests/",
     f"--bundle-id={bundle_id}",
     "-v", "--tb=short"],
    capture_output=True, text=True,
    cwd="/opt/app"
)
print(result.stdout + result.stderr)
```

`cwd="/opt/app"` is required — pytest picks up `conftest.py` from there.

## After writing or changing a bundle

Always run the full suite before shipping. Tests catch broken configs, missing
`SKILL.md` fields, wrong tool aliases, graph compilation errors, and more — all
without needing a running server or any API keys.