---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/canvas/search-operations-README.md
title: "Canvas Pin Search Operations"
summary: "The pin-board search contract: exactly what text is indexed per card (the card-level snapshot, not the source object), when the per-user index is built (one index across all of a user's boards), the faiss vector backend and its files on shared storage, the semantic floor (incl. turning semantic off), the economical guard, and the observability logs."
status: active
tags: ["sdk", "solutions", "canvas", "pins", "search", "index", "faiss", "embeddings", "hybrid-search"]
keywords:
  [
    "canvas_search",
    "CanvasPinSearch",
    "card_text",
    "indexed material",
    "pin index",
    "faiss-local",
    "pins.index.sqlite",
    "pins.index.faiss",
    "card-level snapshot",
    "canvas.pin_search_backend",
    "docs_total log",
  ]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/canvas/pin-operations-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/canvas/pin-integration-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/index/hybrid-index-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/index/hybrid-scoring-README.md
---
# Canvas Pin Search Operations

`canvas_search` is read-only hybrid search over a user's pins — semantic + lexical
+ recency, reciprocal-rank-fused — exposed as the generic `CanvasPinSearch` service
any bundle that mounts the canvas reuses. This page is the precise contract: what
gets indexed, when, on what backend, and how to observe it. The wiring is in
[Pin Integration → Pin Search](./pin-integration-README.md#pin-search); the fusion
math is the generic [hybrid scoring](../index/hybrid-scoring-README.md).

## What is indexed (the card-level snapshot)

The index material is **not the card id** and **not the source object's contents** —
it is a text blob composed from the card's own human-readable fields (`card_text`),
captured at pin/update time. A pin proxies an object in another subsystem that may
be unversioned, so we never re-fetch the source; the index reflects exactly what the
card holds. The blob is newline-joined, in this order (blank fields skipped):

| # | Field | Note |
|---|---|---|
| 1 | **label** | first non-empty of `label` / `map_label` / `title` / `name` |
| 2 | **title** | only if different from the label above |
| 3 | **description** | |
| 4 | **content_preview** | cached display preview, if any |
| 5 | **mime** | |
| 6 | **comments** | each comment's `text`/`body` |
| 7 | **kind** | e.g. `file`, `note`, `canvas`, `memory` |
| 8 | **ref / logical_path** | e.g. `fi:…`, `task:issue:…`, `cnv:…`, `mem:record:…` |

That blob is what gets **embedded** (semantic) and **FTS5-indexed** (lexical);
**recency** comes from the card's `updated_at`/`created_at`. The `card_id` is
metadata only — returned on a hit, never searched.

**So you match on what's visible on the card** — its title, description, your
comments, its kind, and its ref/path. Searching for words that only exist *inside*
the proxied file/issue (never on the card) returns nothing — that's expected. For a
pin `rl_techniques.pdf`, "react actions" matches only if those words are in the
filename, description, or a comment.

## When the index is built

- **On canvas update** (pin add / edit / remove) — `CanvasPinSearch.index` embeds the
  changed cards and (re)builds the vector index, serialized per user with the
  runtime's observed file lock. Because the index file lives on shared storage (EFS),
  that lock is the **cluster critical section** that keeps two replicas from rebuilding
  the same per-user index at once — see
  [synchronization mechanisms](../../../service/synch-mechanisms/critical-section-README.md).
  This is the only place that pays the embedder for pin material. Embed-on-write: only
  new/changed cards are embedded.
- **Lazily on search (self-heal)** — if the active board has zero indexed docs (pins
  predate the indexing wiring, or a fresh process), `canvas_search` builds the index
  from the live cards before searching. Bounds the "search finds nothing because
  nothing was ever indexed" failure; cheap on later searches (embed-on-write).

**Layout-only patches are skipped.** A pure drag / resize (a `canvas_patch` whose ops
are all `move_card` / `resize_card`) changes no indexed text — `card_text` excludes
placement — so the index op is skipped entirely: no embed, no re-sync, no lock taken.
Dragging a card never triggers reindexing. A patch with any content op still indexes.

Search itself is read-only and embeds only the **query**, gated by the economical
guard (see below).

## Vector backends and their files

The index persists to a per-user SQLite DB; the vector backend is pluggable:

| Backend | Selector | Files (per user) | Notes |
|---|---|---|---|
| **faiss (file-backed)** | `faiss-local` (default) | `pins.index.sqlite` + `pins.index.faiss` | the production path. On shared storage (EFS) the files are shared across the cluster; needs faiss + numpy |
| faiss (cross-process) | `faiss-cached` | via `FaissProjectCache` | Redis-coordinated faiss for deployments with no shared FS |
| brute-force | `bruteforce` | `pins.index.sqlite` only | no-dep fallback for tests / no-faiss envs — not a production path |

Backend resolution order: explicit `vector_backend` arg → bundle prop
`canvas.pin_search_backend` → **`faiss-local`**. Files live under:

```
<bundle storage_root>/<tenant>/<project>/<safe(bundle_id)>/.pin-index/<safe(user_id)>/pins.index.sqlite
                                                                                       pins.index.faiss
```

where `<bundle storage_root>` is env `BUNDLE_STORAGE_ROOT` (or
`PLATFORM.APPLICATIONS.BUNDLE_STORAGE_ROOT`, else `<bundles_root>/_bundle_storage`).
The implementation lives in the generic infra: the [hybrid index](../index/hybrid-index-README.md)
(`infra/index/sqlite`) with backends in `infra/index/vector_store` (brute-force) and
`infra/index/faiss` (faiss — the index *uses* faiss, it does not contain it).

## Economical guard

The query embed costs money, so the semantic pass is gated by the shared
`search_semantic_guard(flow="canvas.pins.search")` — the same verify-only
`economic_preflight` gate memory and task-tracker search use. On denial (or for a
trivial query), search degrades to lexical + recency at zero embed cost. Indexing
(write-side embeds) is never gated; the board always stays indexed. Tuning knobs
(weights, RRF k, recency half-life, semantic floor) are in
[hybrid scoring](../index/hybrid-scoring-README.md).

### Semantic floor / turning semantic off

`CanvasPinSearch(min_semantic_score=…)` (or bundle prop
`canvas.pin_search_min_semantic_score`, or a per-call `payload["min_semantic_score"]`)
sets the semantic relevance floor — default `0.30` so an unrelated query doesn't
match the whole board (the filter/dim UX needs a real boundary). Pass a **negative**
value (e.g. `-1`) to turn the semantic factor **off** entirely and run on lexical +
recency only — for a bundle with no embeddings or no budget. The three regimes
(`< 0` off / `= 0` no-floor / `> 0` floor) are documented in
[hybrid scoring](../index/hybrid-scoring-README.md#min_semantic_score--one-knob-three-regimes).

## Observability

Index and search log to `kdcube.canvas.pins` with the absolute DB path and counts:

```
[canvas.pins.index]  board=<id> cards=<n> docs_total=<n> db=<abs path>
[canvas.pins.search] q='<query>' scope=<board|all_boards> docs_total=<n> results=<n> db=<abs path>
[canvas.pins.search] lazy-built board=<id> cards=<n> docs_total=<n> db=<abs path>
```

`docs_total=0` on a search means nothing is indexed for that scope — distinguishes
"empty index" from "indexed but no match for this query".
