---
id: ks:docs/sdk/bundle/bundle-lifecycle-README.md
title: "Bundle Lifecycle"
summary: "How a bundle is discovered, loaded, initialized, invoked, and what storage/config surfaces are available across those phases."
tags: ["sdk", "bundle", "lifecycle", "storage", "configuration", "entrypoint"]
keywords: ["agentic_workflow", "on_bundle_load", "execute_core", "pre_run_hook", "post_run_hook", "singleton", "bundle_props", "bundle_storage_root"]
see_also:
  - ks:docs/sdk/bundle/bundle-dev-README.md
  - ks:docs/sdk/bundle/bundle-config-README.md
  - ks:docs/sdk/bundle/bundle-storage-cache-README.md
  - ks:docs/sdk/bundle/bundle-knowledge-space-README.md
---
# Bundle Lifecycle

This doc explains the **runtime lifecycle** of a bundle and the **storage/config surfaces** available to it.

## Mental model

Write bundle code as **stateless per invocation**.

Even if a deployment enables singleton reuse, durable bundle state should live in:
- bundle props
- secrets
- Redis KV cache
- bundle storage backend
- shared local bundle storage

Do **not** rely on Python instance fields as durable cross-request state.

## Lifecycle at a glance

```mermaid
flowchart TD
    R[Bundle registry entry] --> D[@agentic_workflow discovery]
    D --> I[Instantiate entrypoint]
    I --> L[on_bundle_load once per process per tenant/project]
    L --> Q[Incoming turn or operation request]
    Q --> B[Refresh request context + bundle props]
    B --> P[pre_run_hook]
    P --> E[execute_core]
    E --> O[post_run_hook]
```

## Main phases

| Phase | When | What happens |
|---|---|---|
| Discovery | Proc startup / bundle load | Loader imports the bundle module and finds the class decorated with `@agentic_workflow` |
| Instantiation | Per request by default | Entrypoint instance is created with `config`, `comm_context`, `pg_pool`, `redis` |
| One-time init | Once per process per tenant/project | `on_bundle_load(...)` may prepare indexes, local caches, repos, or other bundle-local assets |
| Request prep | Every invocation | Request-bound context is refreshed, bundle props are loaded/merged, hooks can run |
| Execution | Every invocation | `execute_core(...)` handles the turn or operation |
| Completion | Every invocation | `post_run_hook(...)` can finalize bookkeeping |

## Instance lifetime

### Default mental model

Treat each incoming chat turn or operation call as a fresh invocation:
- one request
- one execution path
- one result

### Singleton reuse

The registry may enable `singleton=true`.

If that happens:
- the entrypoint instance may be reused
- `rebind_request_context(...)` refreshes request-bound objects such as `comm_context`
- `on_bundle_load(...)` still runs only once per process per tenant/project

Even with singleton reuse, you should still treat runtime memory as ephemeral and non-authoritative.

## Entrypoint methods and timing

| Method | Frequency | Purpose |
|---|---|---|
| `on_bundle_load(**kwargs)` | once per process per tenant/project | build indexes, warm caches, clone repos, prepare local read-only assets |
| `pre_run_hook(state=...)` | every invocation | last-minute validation or reconciliation |
| `execute_core(state=..., thread_id=..., params=...)` | every invocation | main bundle logic |
| `post_run_hook(state=..., result=...)` | every invocation | final bookkeeping |
| `rebind_request_context(...)` | singleton reuse only | refresh request-local handles on cached instance |

Important:
- `on_bundle_load(...)` is intended to be deterministic and idempotent
- do not store request-local state there
- use storage for durable state, not instance fields

## Storage and isolation surfaces

| Surface | Access | Isolation | Use it for |
|---|---|---|---|
| `bundle_props` | read | tenant + project + bundle | effective non-secret configuration |
| `get_secret(...)` | read | secret key namespace | API keys, tokens, credentials |
| Redis KV cache | read/write | whatever keys you choose | lightweight distributed state, flags, small caches |
| Bundle storage backend (`CB_BUNDLE_STORAGE_URL`) | read/write | tenant + project + bundle | persistent bundle data on file/S3 storage |
| Shared local bundle storage (`BUNDLE_STORAGE_ROOT`) | read/write by bundle code | tenant + project + bundle | large local/EFS caches, cloned repos, indexes, read-only assets |
| Current turn `OUT_DIR` / `workdir` | read/write during execution | current invocation | transient turn files, generated artifacts, isolated exec inputs/outputs |

## Storage diagram

```text
Bundle developer surfaces

  Config / identity
    bundle_props
    get_secret(...)
    comm_context.actor.{tenant_id, project_id, user_id, ...}

  Distributed state
    Redis KV cache
    CB_BUNDLE_STORAGE_URL-backed storage

  Local shared state
    BUNDLE_STORAGE_ROOT/<tenant>/<project>/<bundle_id>/
      indexes/
      repos/
      caches/
      assets/

  Per-invocation execution state
    OUT_DIR / WORKDIR
```

## User, tenant, and request context

Bundle code can access request identity through the request context:
- tenant
- project
- user / actor metadata
- conversation and turn ids

This context is request-bound. Do not cache it as durable bundle state.

## React integration

If a bundle uses the React agent:
- teach the agent bundle-specific behavior with skills
- expose bundle tools via `tools_descriptor.py`
- optionally expose `ks:` as a read-only logical namespace
- optionally back `ks:` from shared local bundle storage

See:
- [bundle-knowledge-space-README.md](bundle-knowledge-space-README.md)
- [../agents/react/react-turn-workspace-README.md](../agents/react/react-turn-workspace-README.md)

## Practical rules

- Use `on_bundle_load(...)` for heavy preparation that should happen before requests rely on it.
- Persist durable state in storage, not on `self`.
- Use shared local bundle storage for large local reusable assets.
- Use the bundle storage backend or Redis for distributed state that must survive host changes.
- Treat `OUT_DIR` and `workdir` as per-invocation execution state, not bundle state.
