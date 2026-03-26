---
title: "Bundle Tests"
summary: "Checklist of tests that verify a bundle works correctly."
tags: ["sdk", "bundle", "testing"]
keywords: ["bundle tests", "verification", "integration", "error handling", "accounting"]
see_also:
  - ks:docs/sdk/bundle/bundle-dev-README.md
  - ks:docs/sdk/tests/bundle-testing-system-README.md
---

# Bundle Tests

Tests that verify a bundle works correctly from initialization to response.

## How to run

```bash
cd app/ai-app/services/kdcube-ai-app
pytest kdcube_ai_app/apps/chat/sdk/bundle_tests/ --bundle-id=react.doc -v
```

Replace `react.doc` with any available bundle ID: `react`, `openrouter-data`, `eco`.

---

## Test categories

### 1. Initialization
**File:** `test_initialization.py`

- Bundle initializes with valid config, redis, comm_context
- LangGraph compiles after initialization
- `configuration` property returns dict with `role_models`
- Bundle handles None redis (falls back to defaults)
- Event filter initialized (if provided)

### 2. Configuration
**File:** `test_configuration.py`

- Default `role_models` applied from code
- External config overrides respected
- `bundle_prop("some.path")` returns correct value
- Missing config paths return None, not KeyError
- `refresh_bundle_props()` merges Redis overrides
- Redis overrides take precedence over defaults

### 3. Graph
**File:** `test_graph.py`

- `_build_graph()` returns compiled StateGraph
- Graph can be invoked with valid BundleState
- Graph produces `final_answer` and `followups`
- All nodes connected (no orphans)
- Build completes fast (< 1s)

### 4. BundleState
**File:** `test_bundle_state.py`

- All required fields preserved: `request_id`, `tenant`, `project`, `user`
- `final_answer` populated after execution
- `followups` populated after execution
- `error_message` set if error occurs
- `attachments` handled correctly
- State doesn't leak between requests

### 5. Error Handling
**File:** `test_error_handling.py`

- Node exceptions caught, not propagated
- `error_message` set in state when error occurs
- `chat.error` event emitted
- Error message is user-friendly (no stack trace)
- `EconomicsLimitException` NOT caught (re-raised)
- Error doesn't crash the system

### 6. Event Streaming
**File:** `test_event_streaming.py`

- First event has `status="running"` or `status="started"`
- Last event has `status="done"` or `status="error"`
- Events include model name and metadata
- Event filter applied before emit (if provided)
- Events in logical order: start → processing → done

### 7. Accounting
**File:** `test_accounting.py`

- LLM calls wrapped in accounting context
- Done event includes `usage` dict
- `usage` contains `prompt_tokens`, `completion_tokens`, `total_tokens`
- Multiple LLM calls tracked separately
- Over-budget requests rejected with `EconomicsLimitException`

### 8. Storage
**File:** `test_storage.py`

- `bundle_storage_root()` returns correct path
- Path includes tenant/project/bundle_id
- `on_bundle_load()` creates storage directories (if implemented)
- Redis unavailable → graceful fallback to defaults

### 9. Model Routing
**File:** `test_model_routing.py`

- Default model used if no override
- Config override respected
- Redis override respected (takes precedence)
- Switching models works (Claude → OpenRouter, etc.)

### 10. Execution Flow
**File:** `test_execution_flow.py`

- Sequential requests work (no state leakage)
- Multiple concurrent requests don't interfere

### 11. Custom Tools
**Files:** `test_custom_tools_registration.py`, `test_custom_tools_execution.py`, `test_custom_tools_storage.py`, `test_custom_tools_integration.py`

- Tool registers with Tools Subsystem correctly
- Tool accessible via `bundle.get_tool("tool_name")`
- Tool executes with valid inputs and returns expected output
- Tool errors caught and reported (not propagated)
- Tool ID format correct: `<alias>.<tool_name>` or `mcp.<alias>.<tool_name>`
- Multiple custom tools don't conflict

### 12. Custom Skills
**Files:** `test_custom_skills_registration.py`, `test_custom_skills_manifest.py`, `test_custom_skills_visibility.py`, `test_custom_skills_execution.py`

- Skill registers with Skills Subsystem correctly
- `SKILL.md` file exists with valid frontmatter
- `tools.yaml` and `sources.yaml` valid (if provided)
- Skill visibility controlled via `AGENTS_CONFIG`
- Skill instruction injected into LLM prompt

### 13. Storage: Cloud (S3)
**File:** `test_storage_cloud.py`

- Read/write files from S3
- File paths include tenant/project/bundle_id
- Non-existent files return proper error (not crash)
- Path traversal rejected

### 14. Storage: Local FS
**File:** `test_storage_local_fs.py`

- Read/write to local FS
- Temporary files cleaned up after execution
- Isolation between different bundle instances

### 15. Storage: Redis Cache
**File:** `test_storage_redis.py`

- Bundle reads/writes config via Redis
- TTL set correctly (`KV_CACHE_TTL_SECONDS`)
- Namespace isolation works (tenant/project/bundle)
- Redis unavailable → fallback to defaults
- Expired/missing keys handled gracefully

### 16. Storage: Integration
**File:** `test_storage_integration.py`

- Multi-storage workflow works (Redis → Local FS → Cloud)
- Storage paths properly scoped to bundle context
- Cross-tenant access prevented
- Concurrent storage access works