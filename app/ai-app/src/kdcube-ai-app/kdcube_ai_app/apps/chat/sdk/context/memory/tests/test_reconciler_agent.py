from __future__ import annotations

from datetime import datetime, timezone

from kdcube_ai_app.apps.chat.sdk.context.memory.models import MemoryRecord, MemoryScope
from kdcube_ai_app.apps.chat.sdk.context.memory.reconciler_agent import (
    MemoryReconciliationAction,
    MemoryReconciliationOut,
    build_reconciliation_system_prompt,
    candidate_from_memory_record,
    validate_reconciliation_output,
)


def _record(memory_id: str, memory: str, *, context: str = "") -> MemoryRecord:
    now = datetime(2026, 5, 13, tzinfo=timezone.utc)
    return MemoryRecord(
        id=memory_id,
        scope=MemoryScope(tenant="demo", project="demo", user_id="user-1", bundle_id="bundle@1"),
        memory=memory,
        context=context,
        kind="preference",
        status="active",
        visibility="user",
        labels=["Style", "style", " Reports "],
        keywords=["Telegram", "telegram"],
        tier=1,
        pinned=False,
        confidence_score=0.9,
        importance_score=0.8,
        freshness_score=1.0,
        salience_score=0.86,
        confirmation_rate=0.75,
        evidence_count=4,
        update_count=4,
        confirmation_count=3,
        contradiction_count=0,
        created_at=now,
        updated_at=now,
        last_event_at=now,
        last_confirmed_at=now,
        revision=2,
    )


def test_candidate_from_memory_record_is_compact_and_normalized() -> None:
    candidate = candidate_from_memory_record(
        _record(
            "mem_1",
            "User prefers short Telegram summaries",
            context="x" * 1200,
        ),
        context_max_chars=80,
    )

    assert candidate.id == "mem_1"
    assert candidate.context.endswith("...")
    assert len(candidate.context) <= 80
    assert candidate.labels == ["style", "reports"]
    assert candidate.keywords == ["telegram"]
    assert candidate.last_confirmed_at == "2026-05-13T00:00:00+00:00"


def test_validate_reconciliation_output_rejects_unknown_ids_and_low_confidence_merges() -> None:
    output = MemoryReconciliationOut(
        actions=[
            MemoryReconciliationAction(
                action="merge",
                source_memory_id="mem_1",
                target_memory_id="mem_2",
                confidence=0.91,
                reason="same preference",
            ),
            MemoryReconciliationAction(
                action="merge",
                source_memory_id="mem_1",
                target_memory_id="mem_missing",
                confidence=0.91,
                reason="unknown target",
            ),
            MemoryReconciliationAction(
                action="merge",
                source_memory_id="mem_1",
                target_memory_id="mem_2",
                confidence=0.2,
                reason="too weak",
            ),
        ]
    )

    validated = validate_reconciliation_output(output, candidate_ids=["mem_1", "mem_2"])

    assert [action.action for action in validated.actions] == ["merge"]
    assert validated.actions[0].source_memory_id == "mem_1"
    assert len(validated.warnings) == 2


def test_system_prompt_keeps_reconciler_as_proposal_agent() -> None:
    prompt = build_reconciliation_system_prompt(max_actions=5)

    assert "propose safe maintenance actions" in prompt
    assert "Do not rewrite memories" in prompt
    assert "Return at most 5 actions" in prompt
