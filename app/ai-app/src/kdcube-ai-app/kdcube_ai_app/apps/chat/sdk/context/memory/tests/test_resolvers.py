from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from kdcube_ai_app.apps.chat.sdk.context.memory.models import MemoryRecord, MemoryScope
from kdcube_ai_app.apps.chat.sdk.context.memory.events.resolver import (
    canonical_memory_ref,
    memory_id_from_ref,
    memory_ref,
    memory_ref_capabilities,
    resolve_memory_ref_action,
)


class _Store:
    def __init__(self, record: MemoryRecord | None) -> None:
        self.record = record
        self.calls = []

    async def get_memory(self, **kwargs):
        self.calls.append(kwargs)
        return self.record


def _record(memory_id: str = "mem_1") -> MemoryRecord:
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    scope = MemoryScope(tenant="demo", project="project", user_id="user_1", bundle_id="bundle@1")
    return MemoryRecord(
        id=memory_id,
        scope=scope,
        memory="Use concise status updates",
        context="The user prefers short progress notes.",
        kind="preference",
        status="active",
        visibility="user",
        labels=("communication",),
        keywords=("status",),
        tier=1,
        pinned=False,
        confidence_score=0.9,
        importance_score=0.8,
        freshness_score=1.0,
        salience_score=0.85,
        confirmation_rate=1.0,
        evidence_count=2,
        update_count=0,
        confirmation_count=1,
        contradiction_count=0,
        created_at=now,
        updated_at=now,
        last_event_at=now,
        revision=3,
    )


def test_memory_ref_helpers_are_namespace_owned():
    assert memory_id_from_ref("mem:mem_123#x") == "mem_123"
    assert memory_id_from_ref("mem:record:mem_123#x") == "mem_123"
    assert memory_id_from_ref("me:mem_123#x") == "mem_123"
    assert memory_ref("mem_123") == "mem:record:mem_123"
    assert canonical_memory_ref("me:mem_123") == "mem:record:mem_123"
    assert canonical_memory_ref("plain_id") == ""
    assert memory_ref_capabilities() == {"preview": True, "open": True, "download": False, "rehost": False}


def test_memory_resolver_preview_reads_memory_store():
    record = _record()
    store = _Store(record)
    result = asyncio.run(resolve_memory_ref_action(
        {"object_ref": "me:mem_1", "action": "preview"},
        store=store,  # type: ignore[arg-type]
        scope=record.scope,
    ))

    assert result["ok"] is True
    assert result["resolver"] == "sdk.memory"
    assert result["namespace"] == "mem"
    assert result["object_kind"] == "memory.record"
    assert result["object_ref"] == "mem:record:mem_1"
    assert result["memory"]["id"] == "mem_1"
    assert result["memory"]["object_ref"] == "mem:record:mem_1"
    assert result["title"] == "Use concise status updates"
    assert store.calls[0]["memory_id"] == "mem_1"
    assert store.calls[0]["visible_to_user"] is True


def test_memory_resolver_open_returns_ui_open_event():
    record = _record()
    result = asyncio.run(resolve_memory_ref_action(
        {"object_ref": "mem:record:mem_1", "action": "open"},
        store=_Store(record),  # type: ignore[arg-type]
        scope=record.scope,
    ))

    assert result["ok"] is True
    assert result["default_open_effect_action"] == "open"
    assert result["object_kind"] == "memory.record"
    assert result["object_ref"] == "mem:record:mem_1"
    assert result["ui_event"]["target_surface"] == "sdk.memory.viewer"
    assert result["ui_event"]["object_ref"] == "mem:record:mem_1"
    assert result["ui_event"]["memory_id"] == "mem_1"


def test_memory_resolver_missing_ref_is_bounded_error():
    scope = MemoryScope(tenant="demo", project="project", user_id="user_1", bundle_id="bundle@1")
    result = asyncio.run(resolve_memory_ref_action(
        {"object_ref": "not-memory", "action": "preview"},
        store=_Store(None),  # type: ignore[arg-type]
        scope=scope,
    ))

    assert result["ok"] is False
    assert result["error"] == "object_ref_required"


class _FamilyScopedStore(_Store):
    """Returns the record only for identity-family reads (user_ids provided).

    Mirrors the live failure: the record's owning identity differs from the
    caller's primary identity, so a single-actor lookup misses while the
    family read finds it.
    """

    def __init__(self, record: MemoryRecord, owner_user_id: str) -> None:
        super().__init__(record)
        self.owner_user_id = owner_user_id

    async def get_memory(self, **kwargs):
        self.calls.append(kwargs)
        user_ids = kwargs.get("user_ids") or []
        scope = kwargs.get("scope")
        if self.owner_user_id in set(user_ids):
            return self.record
        if scope is not None and scope.user_id == self.owner_user_id:
            return self.record
        return None


def test_memory_resolver_open_uses_identity_family_read_scope():
    # The exact surfaced case: the memory was created under a LINKED identity
    # (e.g. a messenger-linked account) and under the memories app's bundle,
    # while the opener calls through ANOTHER bundle with the family's primary
    # identity. object.action(open) must resolve it exactly like object.get:
    # with the identity-family user_ids and without bundle narrowing.
    record = _record()
    owner = "telegram_434804821"
    record = MemoryRecord(**{
        **record.__dict__,
        "scope": MemoryScope(
            tenant="demo", project="project",
            user_id=owner, bundle_id="user-memories@2026-06-26",
        ),
    })
    store = _FamilyScopedStore(record, owner_user_id=owner)
    caller_scope = MemoryScope(
        tenant="demo", project="project",
        user_id="cognito_user_primary", bundle_id="workspace@2026-03-31-13-36",
    )

    # Family read scope supplied (provider object.get parity) → resolves.
    result = asyncio.run(resolve_memory_ref_action(
        {"object_ref": "mem:record:mem_1", "action": "open"},
        store=store,  # type: ignore[arg-type]
        scope=caller_scope,
        scope_filter="all_user_memories",
        user_ids=("cognito_user_primary", owner),
    ))
    assert result["ok"] is True
    assert result["ui_event"]["target_surface"] == "sdk.memory.viewer"
    assert store.calls[-1]["user_ids"] == ("cognito_user_primary", owner)
    assert store.calls[-1]["scope_filter"] == "all_user_memories"

    # The single-actor regression shape answers memory_not_found — the exact
    # live failure this test pins down.
    missing = asyncio.run(resolve_memory_ref_action(
        {"object_ref": "mem:record:mem_1", "action": "open"},
        store=store,  # type: ignore[arg-type]
        scope=caller_scope,
        scope_filter="all_user_memories",
    ))
    assert missing["ok"] is False
    assert missing["error"] == "memory_not_found"
