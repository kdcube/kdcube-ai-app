---
title: "Bundle Tests Reference"
summary: "What each test file covers and what it validates."
tags: ["sdk", "bundle", "testing"]
keywords: ["bundle tests", "test files", "coverage"]
see_also:
  - ks:docs/sdk/tests/how-it-works-README.md
  - ks:docs/sdk/tests/bundle-testing-system-README.md
---

# Bundle Tests Reference

22 test files, 244 tests total. Each file covers one area of bundle behavior.

## Core bundle

| File | What it checks |
|---|---|
| `test_initialization.py` | Bundle loads, LangGraph compiles, config present |
| `test_graph.py` | Graph nodes/edges connected, no orphans, `ainvoke` works |
| `test_configuration.py` | `role_models` defaults, `bundle_prop()` navigation, Redis overrides |
| `test_model_routing.py` | Roles map to correct provider/model, overrides respected |
| `test_bundle_state.py` | Required fields preserved, no state leakage between requests |
| `test_execution_flow.py` | `execute_core()` / `pre_run_hook()` / `post_run_hook()` exist and are callable |
| `test_error_handling.py` | Exceptions produce `error_message`, `chat.error` event emitted, `EconomicsLimitException` re-raised |
| `test_event_streaming.py` | Event sequence (start → running → complete), envelope fields, event filter |
| `test_accounting.py` | Token tracking, `AccountingContext`, `price_table()`, `EconomicsLimitException` |

## Custom skills

| File | What it checks |
|---|---|
| `test_custom_skills_registration.py` | `skills_descriptor.py` defines `CUSTOM_SKILLS_ROOT`, `SkillsSubsystem` loads skills |
| `test_custom_skills_manifest.py` | Every `SKILL.md` has valid frontmatter (`name`, `id`, `description`), `tools.yaml` / `sources.yaml` parse correctly |
| `test_custom_skills_execution.py` | `SKILL.md` body is non-empty, `get_skill()` resolves registered skills |
| `test_custom_skills_visibility.py` | `AGENTS_CONFIG` structure, `SkillsSubsystem` visibility filtering |

## Custom tools

| File | What it checks |
|---|---|
| `test_custom_tools_registration.py` | `TOOLS_SPECS` aliases unique, each has `module`/`ref`, `TOOL_RUNTIME` values valid |
| `test_custom_tools_execution.py` | `parse_tool_id()` parsing, SDK tool modules importable, runtime resolution |
| `test_custom_tools_integration.py` | Tool IDs don't collide, graph exposes `ainvoke` and `get_graph()` |
| `test_custom_tools_storage.py` | `AIBundleStorage` write/read/delete, tenant isolation, path traversal rejected |

## Storage

| File | What it checks |
|---|---|
| `test_storage.py` | `bundle_storage_root()` path includes tenant/project/bundle_id |
| `test_storage_local_fs.py` | Local FS write/read/delete, isolation between bundle instances |
| `test_storage_cloud.py` | S3-like write/read/delete, URI structure, error handling |
| `test_storage_redis.py` | `refresh_bundle_props()` fallback, `_deep_merge_props()`, kv_cache overrides |
| `test_storage_integration.py` | Cross-tenant/project/bundle isolation, concurrent access, full lifecycle |