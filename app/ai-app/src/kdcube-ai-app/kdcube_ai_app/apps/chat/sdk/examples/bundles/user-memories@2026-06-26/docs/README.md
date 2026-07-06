---
id: user-memories@2026-06-26/docs
title: "User Memories — Design, Storages & Dataflows"
summary: "Why a dedicated memory app, what it owns vs. derives, and the storages + dataflows behind the memories widget and the `mem` named service."
status: active
tags: ["design", "memory", "storages", "dataflows", "named-service"]
---

# User Memories — Design

## Problem

Several apps want to show the user's memories. Today each one **embeds the
memory module** and republishes the widget (e.g. `workspace`). That duplicates
the widget build, the operations surface, and the wiring in every app, and makes
"where do memories live" ambiguous.

## Decision

Expose memories from **one** app:

- it **owns** the memories widget surface and the `mem` named service;
- every other app **embeds the widget by iframe** and **consumes `mem`** as a
  named service.

Because memories are **user-scoped** (keyed by platform user id), the same
records appear wherever the widget or the `mem` service is used — so a single
hosting app is sufficient and correct.

## What this app owns vs. derives

- **Derives** (from `BaseEntrypointWithEconomicsAndMemory`): all memory widget
  operations, the `mem` named-service provider + Redis discovery, reconciliation,
  snapshots, schema-ensure, and the economics guard.
- **Owns**: only the configuration that enables the widget and sets its scope,
  plus this documentation. No domain code, no UI, no storage of its own.

## Storages

| Store | Backend | Scope | Lifecycle |
|-------|---------|-------|-----------|
| User memories | Postgres (tenant/project), with embeddings | per user | schema ensured on first widget use; durable |
| Reconciliation jobs | bundle artifact storage `memory/reconciliation/jobs` | per user/job | retention-bounded (`memory.reconciliation.retention_days`) |
| Snapshots | bundle artifact storage `memory/snapshots` | per user | capped (`memory.snapshots.max_snapshots`, `retention_days`) |

The memory store is **not** this app's private store — it is the platform
user-memory store, shared by intent. This app never writes app-private domain
rows.

## Dataflows

1. **Widget read/write** — the iframe calls `memories_widget_data/_create/_update/_delete`;
   these hit the user-memory store (hybrid lexical+semantic search on read).
2. **Reconcile / snapshot** — `memories_widget_reconcile_*` / `_snapshot_*` reserve
   budget through the economics guard, then write job/snapshot artifacts.
3. **Cross-app** — a consuming app's agent calls the `mem` named service
   (`object.search/get/create/update/delete`) against the same store, with no
   module embedding.

## Non-goals

- No chat product / agent here (the graph is a no-op).
- No app-local UI copy of the widget (single SDK source only).
- No second economics guard or memory store.

## Migration (tracked in README "Roadmap")

`workspace` → consume `mem` as a named service + iframe this widget; then the
site scene points its memory component here. Done step by step, not at once.
