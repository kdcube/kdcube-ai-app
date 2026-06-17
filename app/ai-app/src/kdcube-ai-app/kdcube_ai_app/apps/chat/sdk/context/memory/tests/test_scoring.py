from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from kdcube_ai_app.apps.chat.sdk.context.memory.models import MemoryScope, MemorySearchRequest, normalize_scope_filter, normalize_terms
from kdcube_ai_app.apps.chat.sdk.context.memory.scoring import (
    build_canonical_key,
    compute_confirmation_rate,
    compute_freshness_score,
    compute_memory_scores,
    compute_tier,
    rank_candidate,
    search_query_terms,
    token_overlap_score,
)
from kdcube_ai_app.apps.chat.sdk.context.memory.store import UserMemoryStore


def test_normalize_terms_deduplicates_and_strips() -> None:
    assert normalize_terms("Urgent, urgent, Billing ,") == ["urgent", "billing"]


def test_normalize_scope_filter_defaults_to_current_bundle() -> None:
    assert normalize_scope_filter("") == "current_bundle"
    assert normalize_scope_filter("bundle only") == "current_bundle"
    assert normalize_scope_filter("all") == "all_user_memories"
    assert normalize_scope_filter("global") == "global_only"


def test_search_query_terms_drop_filler_words() -> None:
    assert search_query_terms("cities which i visit") == ["cities", "visit"]


def test_token_overlap_uses_meaningful_query_terms() -> None:
    text = "The city where we live now is Wuppertal. Other relevant cities: Essen and Dusseldorf. Sometimes we visit."
    assert token_overlap_score("cities which i visit", text) == 1.0
    assert token_overlap_score("cats dogs pets", text) == 0.0


def test_canonical_key_is_stable_for_spacing_and_case() -> None:
    left = build_canonical_key(user_id="U1", kind="Preference", memory="  Likes short answers ", labels=["Style"])
    right = build_canonical_key(user_id="u1", kind="preference", memory="likes   short answers", labels=["style"])
    assert left == right


def test_confirmation_rate_balances_positive_and_negative_updates() -> None:
    assert compute_confirmation_rate(confirmation_count=3, contradiction_count=0, update_count=3) > 0.8
    assert compute_confirmation_rate(confirmation_count=1, contradiction_count=3, update_count=4) < 0.4


def test_freshness_score_decays_by_half_life() -> None:
    now = datetime(2026, 5, 11, tzinfo=timezone.utc)
    fresh = compute_freshness_score(now, now=now, half_life_days=10)
    old = compute_freshness_score(now - timedelta(days=10), now=now, half_life_days=10)
    assert fresh == 1.0
    assert 0.49 < old < 0.51


def test_scores_promote_confirmed_fresh_memories_to_tier_one() -> None:
    scores = compute_memory_scores(
        status="active",
        positive_weight=6.0,
        negative_weight=0.0,
        evidence_count=4,
        confirmation_count=3,
        contradiction_count=0,
        update_count=4,
        current_importance=0.8,
        signal_importance=0.9,
        last_event_at=datetime.now(timezone.utc),
    )
    assert scores["tier"] == 1
    assert scores["salience_score"] >= 0.72


def test_weakened_memory_cannot_be_tier_one() -> None:
    assert (
        compute_tier(
            status="weakened",
            confidence_score=1.0,
            salience_score=1.0,
            confirmation_rate=1.0,
            update_count=10,
            pinned=True,
        )
        == 3
    )


def test_pinned_active_memory_is_tier_one_without_multiple_events() -> None:
    assert (
        compute_tier(
            status="active",
            confidence_score=0.2,
            salience_score=0.2,
            confirmation_rate=0.0,
            update_count=1,
            pinned=True,
        )
        == 1
    )


def test_rank_candidate_combines_text_labels_and_salience() -> None:
    score, parts = rank_candidate(
        query="telegram report delivery",
        query_embedding=None,
        requested_labels=["telegram"],
        requested_keywords=[],
        row={
            "memory": "User prefers Telegram delivery for reports",
            "search_text": "User prefers Telegram delivery for reports",
            "labels": ["telegram", "delivery"],
            "keywords": ["report"],
            "confidence_score": 0.9,
            "importance_score": 0.7,
            "salience_score": 0.8,
            "confirmation_rate": 0.75,
            "last_event_at": datetime.now(timezone.utc),
        },
    )
    assert score > 0.35
    assert parts["text"] > 0
    assert parts["labels"] == 1.0
    assert parts["confidence"] == 0.9


class _RankOnlyMemoryStore(UserMemoryStore):
    def __init__(self, rows):
        super().__init__(pg_pool=object(), tenant="tenant-a", project="project-a")
        self._rows = rows

    def _require_pool(self):
        return object()

    async def _fetch_candidates(self, request):
        return list(self._rows)


def _search_row(memory_id: str, *, memory: str, search_text: str, semantic_score: float) -> dict:
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    return {
        "id": memory_id,
        "tenant": "tenant-a",
        "project": "project-a",
        "user_id": "user-a",
        "bundle_id": "bundle@1",
        "memory": memory,
        "search_text": search_text,
        "kind": "fact",
        "status": "active",
        "visibility": "user",
        "labels": [],
        "keywords": [],
        "tier": 2,
        "pinned": False,
        "confidence_score": 0.8,
        "importance_score": 0.8,
        "freshness_score": 1.0,
        "salience_score": 0.8,
        "confirmation_rate": 0.8,
        "evidence_count": 1,
        "update_count": 1,
        "confirmation_count": 1,
        "contradiction_count": 0,
        "created_at": now,
        "updated_at": now,
        "last_event_at": now,
        "semantic_score": semantic_score,
        "text_rank": 0.0,
        "revision": 1,
    }


@pytest.mark.asyncio
async def test_memory_search_factor_weights_can_reorder_same_candidates() -> None:
    store = _RankOnlyMemoryStore(
        [
            _search_row(
                "text-match",
                memory="Legal relationship document wording preference",
                search_text="Legal relationship document wording preference",
                semantic_score=0.0,
            ),
            _search_row(
                "semantic-match",
                memory="Commercial drafting preference",
                search_text="Commercial drafting preference",
                semantic_score=0.4,
            ),
        ]
    )
    request = MemorySearchRequest(
        scope=MemoryScope(tenant="tenant-a", project="project-a", user_id="user-a", bundle_id="bundle@1"),
        query="legal relationship document",
        limit=2,
    )

    default_results = await store.search(request)
    tuned_results = await store.search(
        MemorySearchRequest(
            scope=request.scope,
            query=request.query,
            limit=2,
            factor_weights={"semantic_weight": 1.0},
        )
    )

    assert [result.memory.id for result in default_results] == ["text-match", "semantic-match"]
    assert [result.memory.id for result in tuned_results] == ["semantic-match", "text-match"]
