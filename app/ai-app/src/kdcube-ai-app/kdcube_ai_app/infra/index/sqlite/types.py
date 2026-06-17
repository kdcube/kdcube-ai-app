# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""Public types for the generic SQLite+vector hybrid index."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Sequence

# The pluggable vector backend contract lives one level up — the SQLite index
# *uses* a VectorStore, it does not own the backends. faiss backends are in
# `kdcube_ai_app.infra.index.faiss`.
from ..vector_store import VectorStore  # noqa: F401  (re-exported public type)

# An embedder: text batch -> one vector per text. The platform's
# `model_service.embed_texts` satisfies this exactly.
EmbedFn = Callable[[Sequence[str]], Awaitable[List[List[float]]]]


@dataclass
class Document:
    """A unit to index. `text` is the searchable blob the caller composes
    (e.g. label + summary + description + comments). `metadata` is returned on
    hits and can be filtered on. `timestamp` (epoch seconds) drives recency;
    defaults to now at upsert time."""
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float | None = None


@dataclass
class SearchHit:
    id: str
    score: float
    metadata: Dict[str, Any]
    sub: Dict[str, Any] = field(default_factory=dict)  # per-ranker ranks/scores (telemetry)


@dataclass
class FusionWeights:
    """RRF weights per ranker. Recency is intentionally lighter than the
    content rankers by default."""
    lexical: float = 1.0
    semantic: float = 1.0
    recency: float = 0.5


@dataclass
class IndexConfig:
    db_path: Path
    embed_fn: EmbedFn
    dim: int
    vector_store: VectorStore
    weights: FusionWeights = field(default_factory=FusionWeights)
    rrf_k: int = 60
    recency_half_life_days: float = 30.0
    overfetch: int = 5  # per-ranker candidate multiplier before fusion
    # Semantic relevance floor — three regimes on one knob:
    #   < 0 (e.g. -1) : turn the semantic factor OFF entirely — search runs on
    #                   lexical + recency only (no embed call). The explicit
    #                   "semantic unavailable / don't consider it" choice.
    #   = 0 (default) : semantic ON, no floor — keeps every nearest row. Fine for a
    #                   ranked-list UX; for a match/no-match (filter/dim) UX this
    #                   lets the always-returns-something vector search match all.
    #   > 0 (e.g. 0.3): semantic ON, drop hits at/below this cosine similarity so
    #                   clearly-unrelated docs don't leak in. Use for filter UX.
    min_semantic_score: float = 0.0

    # --- economical guard on semantic search (the embedder call costs money) ---
    # When the guard denies, search degrades to lexical + recency (no embed call).
    semantic_enabled: bool = True              # master switch
    semantic_min_chars: int = 2                # don't embed trivial queries
    # Budget/policy hook: return False to skip the paid embed for this query.
    # Fails closed (an error → skip). May be sync OR async — so it can call the
    # economics engine's `economic_preflight` (the feasibility-only check). This is
    # where the budget/quota enforcement plugs in.
    semantic_guard: Callable[[str], "bool | Awaitable[bool]"] | None = None
    query_cache_size: int = 128                # LRU of query→vector (avoid re-embedding repeats)
