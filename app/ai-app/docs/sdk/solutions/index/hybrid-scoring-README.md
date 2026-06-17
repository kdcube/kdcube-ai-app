---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/index/hybrid-scoring-README.md
title: "Hybrid Scoring: Recency Decay + Reciprocal Rank Fusion"
summary: "The reusable scoring half of the hybrid index: exponential recency decay and weighted Reciprocal Rank Fusion (RRF) over lexical, semantic, and recency rankings, plus the economical guard that gates the paid semantic pass. Used by canvas pins, task-tracker issues, and memory search."
status: active
tags: ["sdk", "solutions", "index", "search", "scoring", "rrf", "recency", "fusion", "economics"]
keywords:
  [
    "reciprocal rank fusion",
    "rrf",
    "recency decay",
    "half-life",
    "fusion weights",
    "hybrid scoring",
    "semantic guard",
    "economic_preflight",
    "search_semantic_guard",
    "min_semantic_score",
    "rrf_k",
    "FusionWeights",
  ]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/index/hybrid-index-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/economics/economic-enforcement-engine-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/canvas/pin-integration-README.md
---
# Hybrid Scoring: Recency Decay + Reciprocal Rank Fusion

This is the scoring mechanism shared by every searchable collection on the
platform — canvas pins, task-tracker issues, memory search. It turns several
independent rankings into one, and it decides when the paid semantic ranking is
worth running. The index lifecycle and vector backends are in
[SQLite + Vector Hybrid Index](./hybrid-index-README.md); this page is the math
and the guard.

The shape is **"semantic + lexical + recency, reciprocal"**: three rankers, each
contributing by rank position, fused with Reciprocal Rank Fusion. It lives in
`kdcube_ai_app/infra/index/sqlite/fusion.py` (pure python, no deps) and is
configured through `FusionWeights` / `IndexConfig`.

## The three rankers

| Ranker | Source | Always runs? |
|---|---|---|
| **lexical** | **SQLite FTS5** `bm25` over the document text | yes (and is the degraded fallback) |
| **semantic** | cosine over embed-on-write vectors — **FAISS** `IndexFlatIP` on L2-normalized vectors (inner product = cosine). The index file lives on the shared filesystem (EFS), so it is shared across the cluster; maintenance (rebuild/write) is serialized with a cluster critical section keyed on the index scope (for canvas pins: per-user, since one index file holds all of a user's boards). A Redis-cached faiss store is the alternative when no shared FS is available. | only when enabled (`min_semantic_score >= 0`) **and** the economical guard clears |
| **recency** | exponential decay on the document timestamp | in `hybrid` mode, over the fused candidate set |

## Recency decay

```python
recency_score(ts, half_life_days=30.0) -> float   # in [0, 1]
```

Exponential half-life decay: `1.0` at now, `0.5` after one half-life,
asymptotically `0`. A missing timestamp scores `0`. Recency is deliberately a
*ranking input*, not a hard sort — a much older but far more relevant document can
still win on the content rankers.

## Reciprocal Rank Fusion (RRF)

Each ranker produces a best-first list of ids. A document's fused score sums, over
the rankers it appears in, a weighted reciprocal of its rank:

```
score(doc) = Σ_ranker  weight[ranker] / (k + rank_in_ranker + 1)
```

- `k` (`IndexConfig.rrf_k`, default **60**) damps the head: it keeps any single
  ranker's #1 from dominating, so agreement across rankers matters more than a
  single ranker's confidence. This is the standard RRF constant.
- Rank position — not the raw bm25 / cosine score — is what's fused, which is why
  incomparable scales (bm25 vs cosine vs decay) combine cleanly.
- Recency is folded in by sorting the candidate ids by `recency_score` and treating
  that order as a third ranking.

### Fusion weights

```python
@dataclass
class FusionWeights:
    lexical: float = 1.0
    semantic: float = 1.0
    recency: float = 0.5   # intentionally lighter than the content rankers
```

Recency defaults to half a content ranker's weight: it nudges ties toward fresher
documents without letting "new" beat "relevant." A ranker with weight `<= 0` is
dropped from fusion.

## The economical guard (gating the semantic pass)

The semantic ranker is the only one that costs money — it calls the embedder. So it
is gated; when the gate denies, search degrades to lexical + recency and pays
nothing. The knobs (`IndexConfig`):

```python
semantic_enabled: bool = True       # master switch
semantic_min_chars: int = 2         # don't embed trivial queries
min_semantic_score: float = 0.0     # semantic relevance floor — see regimes below
semantic_guard: Callable[[str], bool | Awaitable[bool]] | None = None
query_cache_size: int = 128         # LRU of query -> vector (don't re-embed repeats)
```

### `min_semantic_score` — one knob, three regimes

Vector search **always returns the nearest rows** (every document has some positive
cosine to any query), so `min_semantic_score` is not a weight — it is the
semantic arm's **match boundary**:

| Value | Meaning |
|---|---|
| `< 0` (e.g. `-1`) | **Semantic factor OFF** — the arm is skipped entirely; search runs on lexical + recency only, at **no embed cost**. The explicit "semantic unavailable / don't consider it" choice for a scope with no embeddings or no budget. |
| `= 0` (default) | Semantic **on, no floor** — keeps every nearest row. Fine for a *ranked-list* UX; for a *match/no-match* (filter / dim) UX this lets an unrelated query match the whole collection. |
| `> 0` (e.g. `0.3`) | Semantic **on, with floor** — drops hits at/below this cosine. Use for filter/dim UX where "no match" must mean nothing is highlighted. |

Turning the factor off is safe because **lexical has its own intrinsic boundary**
(a document either contains the query tokens or it doesn't) and **recency only
reranks the matched candidate set** — it never widens it. So disabling semantic
narrows you to lexical relevance; it never produces the "everything matches" result.

The semantic arm is also **fail-soft**: if the embedder or vector store errors at
query time, the search logs and degrades to lexical rather than failing — runtime
"semantic unavailable" is handled the same graceful way as an explicit `-1`.

`semantic_guard` is the budget/quota hook. It may be **sync or async**, and it
**fails closed** — any error means "skip the paid embed." Because it can be async,
it plugs directly into the economics engine's feasibility-only check
(`economic_preflight`): the guard returns `True` only if the user can currently
afford the embedding under their limits. See
[Economic Enforcement Engine](../../../economics/economic-enforcement-engine-README.md).

The platform provides one shared guard factory on the chat base entrypoint,
`search_semantic_guard(flow=...)`, which builds exactly this predicate (verify-only
preflight, `False` on `EconomicsLimitException`, `None` → ungated when economics is
off or the user is anonymous). Every collection passes a distinct `flow` label so
spend is attributed per surface.

## Usages

All three share this scoring and differ only by `flow` and how they compose
`Document.text`:

| Collection | Flow label | Notes |
|---|---|---|
| **Canvas pins** | `canvas.pins.search` | per-user SQLite + per-user faiss (`pins.index.faiss`); indexes the card-level snapshot on canvas update; see [Pin Integration](../canvas/pin-integration-README.md) |
| **Task-tracker issues** | `task_tracker.issue.search` | gates both issue search and duplicate-candidate detection |
| **Memory search** | memory flow | the original `_memory_search_embed_or_downgrade` pattern this generalizes |

Write-side embeds (creating/updating an indexed object) are **not** gated — writes
always index; only query-time semantic spend is metered. This keeps the index
correct regardless of budget and meters only the variable, user-driven cost.

## Telemetry

Each `SearchHit.sub` carries the per-ranker rank that produced it
(`{"lexical_rank": n, "semantic_rank": m, "recency_rank": k}`), so a result's
provenance — which rankers surfaced it and how strongly — is inspectable without
re-running the search.
