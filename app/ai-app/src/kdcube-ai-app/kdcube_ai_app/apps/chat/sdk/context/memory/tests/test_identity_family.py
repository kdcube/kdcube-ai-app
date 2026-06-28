"""Identity-family READ aggregation: reads scope to a user_id set, writes stay single-actor."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kdcube_ai_app.apps.chat.sdk.context.memory.models import (
    MemoryScope,
    MemorySearchRequest,
)
from kdcube_ai_app.apps.chat.sdk.context.memory.store import (
    EVENT_TABLE,
    MEMORY_TABLE,
    UserMemoryStore,
    _normalize_user_ids,
    _user_scope_value,
)


_NOW = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)


def _mem_row(memory_id: str, user_id: str) -> dict:
    return {
        "id": memory_id,
        "tenant": "t",
        "project": "p",
        "user_id": user_id,
        "bundle_id": "b@1",
        "canonical_key": f"ck_{memory_id}",
        "memory": f"memory of {user_id}",
        "context": "",
        "kind": "note",
        "status": "active",
        "visibility": "user",
        "visible_to_user": True,
        "labels": [],
        "keywords": [],
        "tier": 2,
        "pinned": False,
        "search_text": f"memory of {user_id}",
        "confidence_score": 0.8,
        "importance_score": 0.6,
        "freshness_score": 1.0,
        "salience_score": 0.8,
        "confirmation_rate": 1.0,
        "evidence_count": 1,
        "update_count": 1,
        "confirmation_count": 0,
        "contradiction_count": 0,
        "positive_weight": 0.5,
        "negative_weight": 0.0,
        "created_at": _NOW,
        "updated_at": _NOW,
        "last_event_at": _NOW,
        "last_confirmed_at": None,
        "source": {},
        "metadata": {},
        "revision": 1,
        "merged_into_id": None,
    }


class _FakeCon:
    """Applies only the user_id scope predicate the read methods build.

    The fake honors the bound user-scope value at $3 (a single id or a list for
    ANY) against an in-memory set of memory rows, which is exactly what the
    identity-family change drives. Other predicates are treated as pass-through.
    """

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.last_sql = ""
        self.last_args: tuple = ()

    def _user_match(self, sql: str, args: tuple, row: dict) -> bool:
        user_value = args[2]
        if "ANY($3" in sql:
            return row["user_id"] in set(user_value)
        return row["user_id"] == user_value

    async def fetchrow(self, sql: str, *args):
        self.last_sql, self.last_args = sql, args
        mem_id = args[3] if len(args) > 3 else None
        for row in self.rows:
            if mem_id is not None and row["id"] != mem_id:
                continue
            if self._user_match(sql, args, row):
                return dict(row)
        return None

    async def fetch(self, sql: str, *args):
        self.last_sql, self.last_args = sql, args
        return [dict(row) for row in self.rows if self._user_match(sql, args, row)]

    async def fetchval(self, sql: str, *args):
        self.last_sql, self.last_args = sql, args
        return len([row for row in self.rows if self._user_match(sql, args, row)])


class _FakePool:
    def __init__(self, con: _FakeCon) -> None:
        self._con = con

    def acquire(self):
        con = self._con

        class _Acq:
            async def __aenter__(self_inner):
                return con

            async def __aexit__(self_inner, *exc):
                return False

        return _Acq()


class _ReadStore(UserMemoryStore):
    def __init__(self, rows: list[dict]) -> None:
        self.con = _FakeCon(rows)
        self.schema = "kdcube"

    def _require_pool(self):
        return _FakePool(self.con)

    # Skip the bundle scope_filter SQL fragment (not under test here).
    def _append_scope_filter(self, *, where, args, scope, scope_filter, table_alias=""):
        return None


_ACTOR = "02e53484-actor"
_LINKED = "telegram_434804821"
_SCOPE = MemoryScope(tenant="t", project="p", user_id=_ACTOR, bundle_id="b@1")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_normalize_user_ids_dedups_and_drops_empty() -> None:
    assert _normalize_user_ids(None) is None
    assert _normalize_user_ids([]) is None
    assert _normalize_user_ids(["", "  "]) is None
    assert _normalize_user_ids(["a", "a", " b ", ""]) == ["a", "b"]


def test_user_scope_value_picks_single_or_set() -> None:
    assert _user_scope_value("actor", None) == ("actor", False)
    assert _user_scope_value("actor", ["actor"]) == (["actor"], True)
    assert _user_scope_value("actor", ["actor", "linked"]) == (["actor", "linked"], True)


# ---------------------------------------------------------------------------
# Store reads
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_count_aggregates_across_family() -> None:
    rows = [_mem_row("mem_a", _ACTOR), _mem_row("mem_b", _LINKED), _mem_row("mem_c", "stranger")]
    store = _ReadStore(rows)
    # Family of two -> sees both their memories, not the stranger's.
    n = await store.count_memories(scope=_SCOPE, user_ids=[_ACTOR, _LINKED])
    assert n == 2
    assert "ANY($3" in store.con.last_sql
    assert store.con.last_args[2] == [_ACTOR, _LINKED]


@pytest.mark.asyncio
async def test_count_single_actor_when_no_family() -> None:
    rows = [_mem_row("mem_a", _ACTOR), _mem_row("mem_b", _LINKED)]
    store = _ReadStore(rows)
    n = await store.count_memories(scope=_SCOPE, user_ids=None)
    assert n == 1  # only the actor's own
    assert "ANY($3" not in store.con.last_sql
    assert store.con.last_args[2] == _ACTOR


@pytest.mark.asyncio
async def test_search_candidates_aggregate_across_family() -> None:
    rows = [_mem_row("mem_a", _ACTOR), _mem_row("mem_b", _LINKED), _mem_row("mem_c", "stranger")]
    store = _ReadStore(rows)
    request = MemorySearchRequest(scope=_SCOPE, mode="recent", user_ids=[_ACTOR, _LINKED])
    candidates = await store._fetch_candidates(request)
    owners = {c["user_id"] for c in candidates}
    assert owners == {_ACTOR, _LINKED}
    assert "ANY($3" in store.con.last_sql


@pytest.mark.asyncio
async def test_get_memory_by_id_within_family() -> None:
    rows = [_mem_row("mem_b", _LINKED)]
    store = _ReadStore(rows)
    # The by-id read resolves a family member's memory when the family is given.
    found = await store.get_memory(scope=_SCOPE, memory_id="mem_b", user_ids=[_ACTOR, _LINKED])
    assert found is not None and found.id == "mem_b"
    # Without the family, the actor cannot see the linked member's record.
    missing = await store.get_memory(scope=_SCOPE, memory_id="mem_b", user_ids=None)
    assert missing is None
