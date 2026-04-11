# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.external_events import build_conversation_external_event_source
from kdcube_ai_app.apps.chat.processor import EnhancedChatRequestProcessor
from kdcube_ai_app.apps.chat.sdk.protocol import ChatTaskPayload


class _FakeRedis:
    def __init__(self):
        self._kv = {}
        self._streams = {}
        self._stream_seq = {}

    async def incr(self, key):
        self._kv[key] = int(self._kv.get(key, 0)) + 1
        return self._kv[key]

    async def xadd(self, key, fields):
        seq = int(self._stream_seq.get(key, 0)) + 1
        self._stream_seq[key] = seq
        stream_id = f"{seq}-0"
        self._streams.setdefault(key, []).append((stream_id, dict(fields or {})))
        return stream_id

    async def lpush(self, key, value):
        self._kv.setdefault("__lists__", {})
        lists = self._kv["__lists__"]
        lists.setdefault(key, []).insert(0, value)
        return len(lists[key])

    async def xrange(self, key, min="-", max="+", count=None):
        items = list(self._streams.get(key, []))
        out = []
        for stream_id, fields in items:
            if min not in ("-", None, ""):
                exclusive = str(min).startswith("(")
                floor = str(min)[1:] if exclusive else str(min)
                if exclusive:
                    if stream_id <= floor:
                        continue
                elif stream_id < floor:
                    continue
            if max not in ("+", None, "") and stream_id > str(max):
                continue
            out.append((stream_id, dict(fields)))
            if count is not None and len(out) >= int(count):
                break
        return out

    async def xread(self, streams, count=None, block=None):
        del block
        out = []
        for key, start in (streams or {}).items():
            items = await self.xrange(key, min=f"({start}" if start not in ("$", None, "") else "-", max="+", count=count)
            if start == "$":
                items = []
            if items:
                out.append((key, items))
        return out

    async def setex(self, key, ttl, value):
        del ttl
        self._kv[key] = value

    async def set(self, key, value, ex=None, nx=False):
        del ex
        if nx and key in self._kv:
            return False
        self._kv[key] = value
        return True

    async def get(self, key):
        return self._kv.get(key)

    async def delete(self, key):
        self._kv.pop(key, None)


@pytest.mark.asyncio
async def test_external_event_source_publish_read_and_owner():
    redis = _FakeRedis()
    source = build_conversation_external_event_source(
        redis=redis,
        tenant="t1",
        project="p1",
        conversation_id="conv1",
    )

    first = await source.publish(
        kind="followup",
        explicit=True,
        target_turn_id="turn_a",
        active_turn_id_at_ingress="turn_b",
        owner_turn_id="turn_b",
        source="ingress.sse",
        text="also include legal cases",
        payload={"message": "also include legal cases"},
    )
    second = await source.publish(
        kind="steer",
        explicit=True,
        active_turn_id_at_ingress="turn_b",
        owner_turn_id="turn_b",
        source="ingress.sse",
        text="change direction",
    )

    items = await source.read_since(0)
    assert [item.sequence for item in items] == [1, 2]
    assert items[0].message_id == first.message_id
    assert items[1].message_id == second.message_id
    assert items[0].text == "also include legal cases"
    assert items[0].stream_id == "1-0"
    assert items[1].stream_id == "2-0"

    lease = await source.acquire_owner(turn_id="turn_b", bundle_id="bundle@1", listener_id="listener_1")
    assert lease.turn_id == "turn_b"
    owner = await source.get_owner()
    assert owner is not None
    assert owner.listener_id == "listener_1"

    refreshed = await source.refresh_owner(listener_id="listener_1", turn_id="turn_b", bundle_id="bundle@1")
    assert refreshed.listener_id == "listener_1"
    owner = await source.get_owner()
    assert owner is not None
    assert owner.turn_id == "turn_b"

    await source.release_owner(listener_id="listener_1")
    assert await source.get_owner() is None


@pytest.mark.asyncio
async def test_external_event_source_claim_promote_and_consume():
    redis = _FakeRedis()
    source = build_conversation_external_event_source(
        redis=redis,
        tenant="t1",
        project="p1",
        conversation_id="conv1",
    )

    first = await source.publish(
        kind="followup",
        source="ingress.sse",
        text="continue with pricing",
        payload={"message": "continue with pricing"},
        task_payload={
            "meta": {"task_id": "task-1", "created_at": 1.0, "instance_id": "ingress-1"},
            "routing": {"bundle_id": "bundle.demo", "session_id": "sess-1", "conversation_id": "conv1", "turn_id": "turn-2"},
            "actor": {"tenant_id": "t1", "project_id": "p1"},
            "user": {"user_type": "registered", "user_id": "u1"},
            "request": {"message": "continue with pricing", "payload": {}},
            "config": {"values": {}},
            "accounting": {"envelope": {}},
            "continuation": {"kind": "followup", "explicit": False},
        },
    )
    await source.publish(
        kind="steer",
        source="ingress.sse",
        text="change direction",
        payload={"message": "change direction"},
    )

    claimed = await source.claim_next_promotable(claimant_id="proc-1")
    assert claimed is not None
    assert claimed.message_id == first.message_id

    await source.mark_promoted(message_id=claimed.message_id, claimant_id="proc-1", task_id="task-1")
    promoted = await source.get_event(claimed.message_id)
    assert promoted is not None
    assert promoted.promoted_task_id == "task-1"

    updated = await source.mark_consumed_up_to(max_sequence=2, turn_id="turn-2")
    assert updated == 2
    first_after = await source.get_event(first.message_id)
    assert first_after is not None
    assert first_after.consumed_by_turn_id == "turn-2"


@pytest.mark.asyncio
async def test_external_event_source_wait_and_cursor_progression():
    redis = _FakeRedis()
    source = build_conversation_external_event_source(
        redis=redis,
        tenant="t1",
        project="p1",
        conversation_id="conv1",
    )

    first = await source.publish(
        kind="followup",
        source="ingress.sse",
        text="first",
        payload={"message": "first"},
        task_payload={
            "meta": {"task_id": "task-1", "created_at": 1.0, "instance_id": "ingress-1"},
            "routing": {"bundle_id": "bundle.demo", "session_id": "sess-1", "conversation_id": "conv1", "turn_id": "turn-2"},
            "actor": {"tenant_id": "t1", "project_id": "p1"},
            "user": {"user_type": "registered", "user_id": "u1"},
            "request": {"message": "first", "payload": {}},
            "config": {"values": {}},
            "accounting": {"envelope": {}},
            "continuation": {"kind": "followup", "explicit": False},
        },
    )
    waited = await source.wait_for_events_after("0-0", block_ms=1)
    assert waited
    assert waited[0].stream_id == first.stream_id

    claimed = await source.claim_next_promotable(claimant_id="proc-1")
    assert claimed is not None
    await source.mark_promoted(message_id=claimed.message_id, claimant_id="proc-1", task_id="task-1")

    second = await source.publish(
        kind="followup",
        source="ingress.sse",
        text="second",
        payload={"message": "second"},
        task_payload={
            "meta": {"task_id": "task-2", "created_at": 2.0, "instance_id": "ingress-1"},
            "routing": {"bundle_id": "bundle.demo", "session_id": "sess-1", "conversation_id": "conv1", "turn_id": "turn-3"},
            "actor": {"tenant_id": "t1", "project_id": "p1"},
            "user": {"user_type": "registered", "user_id": "u1"},
            "request": {"message": "second", "payload": {}},
            "config": {"values": {}},
            "accounting": {"envelope": {}},
            "continuation": {"kind": "followup", "explicit": False},
        },
    )
    claimed_next = await source.claim_next_promotable(claimant_id="proc-2")
    assert claimed_next is not None
    assert claimed_next.message_id == second.message_id


@pytest.mark.asyncio
async def test_processor_promotes_next_external_event_from_shared_log():
    redis = _FakeRedis()
    source = build_conversation_external_event_source(
        redis=redis,
        tenant="t1",
        project="p1",
        conversation_id="conv1",
    )
    current_payload = ChatTaskPayload.model_validate(
        {
            "meta": {"task_id": "task-current", "created_at": 1.0, "instance_id": "proc-1"},
            "routing": {"bundle_id": "bundle.demo", "session_id": "sess-1", "conversation_id": "conv1", "turn_id": "turn-1"},
            "actor": {"tenant_id": "t1", "project_id": "p1"},
            "user": {"user_type": "registered", "user_id": "u1"},
            "request": {"message": "current", "payload": {}},
            "config": {"values": {}},
            "accounting": {"envelope": {}},
            "continuation": {"kind": "regular", "explicit": False},
        }
    )
    next_payload = {
        "meta": {"task_id": "task-next", "created_at": 2.0, "instance_id": "ingress-1"},
        "routing": {"bundle_id": "bundle.demo", "session_id": "sess-1", "conversation_id": "conv1", "turn_id": "turn-2"},
        "actor": {"tenant_id": "t1", "project_id": "p1"},
        "user": {"user_type": "registered", "user_id": "u1"},
        "request": {"message": "followup", "payload": {}},
        "config": {"values": {}},
        "accounting": {"envelope": {}},
        "continuation": {"kind": "followup", "explicit": False},
    }
    event = await source.publish(
        kind="followup",
        source="ingress.sse",
        text="followup",
        payload={"message": "followup"},
        task_payload=next_payload,
    )

    processor = EnhancedChatRequestProcessor.__new__(EnhancedChatRequestProcessor)
    processor.redis = redis
    processor.process_id = 551
    processor.middleware = type("MW", (), {"instance_id": "proc-1", "QUEUE_PREFIX": "chat-ready"})()

    promoted = await processor._promote_next_external_event(current_payload)
    assert promoted is not None
    assert promoted["payload"].routing.turn_id == "turn-2"
    assert redis._kv["__lists__"]["chat-ready:registered"]
    stored = await source.get_event(event.message_id)
    assert stored is not None
    assert stored.promoted_task_id == "task-next"
