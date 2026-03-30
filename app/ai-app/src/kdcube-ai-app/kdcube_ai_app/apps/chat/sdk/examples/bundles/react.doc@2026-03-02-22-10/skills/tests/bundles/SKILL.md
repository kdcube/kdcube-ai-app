---
name: bundles
id: bundles
description: |
  Draft guidance for validating generated bundles against a small reusable pytest smoke suite.
  Use this skill whenever the task is about bundle code generation, modification, extraction,
  repair, review, or validation and the agent needs the current bundle contract and smoke-test
  expectations in front of it.
version: 1.0.0
category: testing
tags:
  - bundles
  - pytest
  - validation
  - exec
  - react-doc
when_to_use:
  - The user asks to generate a new bundle
  - The user asks to modify an existing bundle and verify it still works
  - The user asks to review, repair, extract, or troubleshoot a bundle
  - The user asks how a bundle should be structured or imported
  - The agent needs a quick bundle smoke test before handoff
  - The agent needs to locate the reusable bundle test fixtures in react.doc
author: kdcube
created: 2026-03-20
namespace: tests
---

# Bundle Tests

## Purpose

This skill tells you where the draft reusable bundle smoke tests live and how to run them from isolated exec.
Keep it loaded whenever bundle code is being authored or discussed in detail, not only when pytest is about to run.

Companion loading rule:
- For bundle tasks, load this skill together with `sk:product.kdcube`.
- `sk:product.kdcube` gives the platform/runtime model.
- `sk:tests.bundles` gives the current bundle contract and validation expectations.

## Where the tests are

The reusable test fixtures are exposed by `react.doc` under their real knowledge-space path:
- `ks:src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/tests/...`

That is a real path under one common `ks:` root, not a separate test-only namespace.

These files are intentionally **not** indexed for `react.search_knowledge`.
Do not assume one fixed file path up front.
Instead:
- keep `ks:src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/tests` as the logical base
- use generated exec code plus `bundle_data.resolve_namespace(...)` to browse the subtree
- inspect the discovered README / pytest files that are relevant

## How to use them

1. Read this skill if it is relevant:
   - `react.read(["sk:tests.bundles"])`
2. If needed, open the fixture docs:
   - start from `ks:src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/tests`
   - discover the relevant README / pytest files by browsing from generated exec code
3. In generated exec code:
   - resolve `ks:src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/tests` with `bundle_data.resolve_namespace(...)`
   - browse the returned `physical_path`
   - identify the relevant pytest files for bundle validation
   - run pytest on the discovered test file(s)
4. Set environment variable `BUNDLE_UNDER_TEST` to the generated bundle root.
5. Write the pytest results to `OUTPUT_DIR/...` so they come back to the agent clearly.

## Important protocol detail

`bundle_data.resolve_namespace(...)` returns an exec-only `physical_path`.
That path is valid only inside isolated exec.

If you need later follow-up with `react.read(...)`, keep the original logical base:
- logical base: `ks:src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/tests`
- discovered relative path: whatever the exec-time browse step found
- follow-up logical ref: `f"{logical_base}/{relative_path}"`

## Expected bundle-under-test contract

The current draft smoke test expects:
- `__init__.py`
- `entrypoint.py`
- `tools_descriptor.py`
- `skills_descriptor.py`

It also checks that:
- `entrypoint.py` imports successfully
- `tools_descriptor.py` imports successfully
- `skills_descriptor.py` imports successfully
- `entrypoint.py` defines non-empty `BUNDLE_ID`
- `entrypoint.py` exposes a bundle workflow class derived from `BaseEntrypoint`

Current entrypoint import contract:
- use `from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint import BaseEntrypoint`
- or `from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint_with_economic import BaseEntrypointWithEconomics`
- do not generate or keep legacy imports like `from kdcube_ai_app.apps.chat.sdk.workflow import AIWorkflow`

## Draft execution pattern

In generated exec code, do roughly this:

1. define `logical_base = "ks:src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/tests"`
2. resolve it with `bundle_data.resolve_namespace(logical_base)`
3. browse under `Path(res["ret"]["physical_path"])` and select the relevant pytest file(s)
4. run:
   - `python -m pytest <discovered_test_file>`
5. set:
   - `BUNDLE_UNDER_TEST=<generated bundle root>`
6. write:
   - test summary
   - stdout/stderr
   into files under `OUTPUT_DIR`
