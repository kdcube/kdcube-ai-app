# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""The bundle-local turn-batch fold (``platform/turn_batch.py``).

The lane-wakeup dispatch hands a run-to-completion turn ONE external event
(the prompt), while the user's attachments ride separate lane events of the
same ingress batch. The fold must deliver the whole batch — the exact
surfaced bug was lg-react answering "whats here" blind to the attached
image. Read-only on the lane: nothing here consumes or reserves anything.

Offline tests: the lane source is faked; no redis, no store, no network.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from kdcube_ai_app.apps.chat.external_events import ConversationExternalEvent
from kdcube_ai_app.apps.chat.sdk.protocol import hosted_external_event_attachments
from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def _turn_batch_module():
    _n, m = load_dynamic_module_for_path(BUNDLE_ROOT / "platform" / "turn_batch.py")
    return m


def _attachments_module():
    _n, m = load_dynamic_module_for_path(BUNDLE_ROOT / "platform" / "attachments.py")
    return m


def _prompt_accepted(text: str = "whats here") -> dict:
    return {
        "event_id": "evt-prompt",
        "type": "event.user.prompt",
        "reactive": True,
        "payload": {"mime": "text/plain", "event": {"text": text}},
    }


def _attachment_accepted() -> dict:
    return {
        "event_id": "evt-att",
        "type": "event.user.attachment.file",
        "reactive": True,
        "payload": {
            "mime": "image/png",
            "event": {
                "filename": "photo.png",
                "mime": "image/png",
                "file_index": 0,
                "hosted_uri": "conv/turn_1/files/photo.png",
            },
        },
    }


def _lane_event(*, message_id: str, sequence: int, batch_id: str = "batch-1",
                accepted: dict, consumed_at: float | None = None) -> ConversationExternalEvent:
    return ConversationExternalEvent(
        message_id=message_id,
        batch_id=batch_id,
        kind="external_event",
        created_at=1000.0 + sequence,
        sequence=sequence,
        payload={"text": "", "event": dict(accepted), "is_continuation": False},
        consumed_at=consumed_at,
    )


class _FakeSource:
    def __init__(self, events):
        self._events = list(events)

    async def get_event(self, message_id):
        for item in self._events:
            if item.message_id == message_id:
                return item
        return None

    async def read_since(self, cursor, *, limit=None):
        return list(self._events)


def _wakeup_raw(event_id: str) -> dict:
    return {
        "meta": {"task_id": "task-1", "created_at": 1000.0},
        "routing": {"conversation_id": "conv-1", "session_id": "sess-1", "bundle_id": "bundle-1"},
        "actor": {"tenant_id": "tenant-a", "project_id": "project-a"},
        "user": {"user_id": "user-1", "user_type": "registered"},
        "event_lane": {
            "tenant": "tenant-a",
            "project": "project-a",
            "conversation_id": "conv-1",
            "user_id": "user-1",
            "agent_id": "lg-react",
            "event_id": event_id,
        },
    }


def _entrypoint(event_id: str = "m-prompt") -> SimpleNamespace:
    return SimpleNamespace(
        redis=object(),
        comm_context=SimpleNamespace(bundle_call_context={"event_lane_wakeup": _wakeup_raw(event_id)}),
    )


def test_fold_delivers_the_hosted_attachment_beside_the_prompt():
    """The surfaced case: prompt + hosted PNG in one batch — the fold must
    surface BOTH so the attachment seam finds the image."""
    mod = _turn_batch_module()
    prompt = _lane_event(message_id="m-prompt", sequence=2, accepted=_prompt_accepted())
    attachment = _lane_event(message_id="m-att", sequence=3, accepted=_attachment_accepted())
    mod._lane_source = lambda redis, wakeup: _FakeSource([attachment, prompt])

    state = {"external_events": [_prompt_accepted()]}
    folded = asyncio.run(mod.fold_turn_external_events(_entrypoint(), state))

    assert [item["event_id"] for item in folded] == ["evt-prompt", "evt-att"]
    hosted = hosted_external_event_attachments(folded)
    assert len(hosted) == 1
    assert hosted[0]["hosted_uri"] == "conv/turn_1/files/photo.png"
    assert hosted[0]["mime"] == "image/png"


def test_fold_skips_batch_siblings_a_previous_turn_consumed():
    """A re-woken queued event promotes ALONE: consumed siblings stay out and
    the dispatched events stand untouched."""
    mod = _turn_batch_module()
    consumed_prompt = _lane_event(
        message_id="m-prompt", sequence=2, accepted=_prompt_accepted(), consumed_at=1234.5,
    )
    followup = _lane_event(message_id="m-follow", sequence=4, accepted=_prompt_accepted("and this?"))
    mod._lane_source = lambda redis, wakeup: _FakeSource([consumed_prompt, followup])

    state = {"external_events": [_prompt_accepted("and this?")]}
    folded = asyncio.run(mod.fold_turn_external_events(_entrypoint("m-follow"), state))

    assert folded == [_prompt_accepted("and this?")]


def test_fold_is_inert_without_a_lane_wakeup():
    """Direct invocations (tests, ops) carry no wakeup context — the state's
    events pass through untouched, and the lane is never opened."""
    mod = _turn_batch_module()
    ep = SimpleNamespace(redis=object(), comm_context=SimpleNamespace(bundle_call_context={}))
    state = {"external_events": [_prompt_accepted()]}

    assert asyncio.run(mod.fold_turn_external_events(ep, state)) == [_prompt_accepted()]


def test_fold_fails_open_when_the_lane_read_breaks():
    mod = _turn_batch_module()

    class _BrokenSource:
        async def get_event(self, message_id):
            raise RuntimeError("lane offline")

    mod._lane_source = lambda redis, wakeup: _BrokenSource()
    state = {"external_events": [_prompt_accepted()]}

    folded = asyncio.run(mod.fold_turn_external_events(_entrypoint(), state))

    assert folded == [_prompt_accepted()]


def test_folded_batch_feeds_the_attachment_seam():
    """End-to-end through the bundle's multimodality seam: the folded events
    materialize into one image block (base64 rides the event, no store)."""
    mod = _turn_batch_module()
    seam = _attachments_module()
    accepted = _attachment_accepted()
    # A real 1x1 PNG body so the image normalizer has valid bytes to inspect.
    accepted["payload"]["event"]["base64"] = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
    )
    prompt = _lane_event(message_id="m-prompt", sequence=1, accepted=_prompt_accepted())
    attachment = _lane_event(message_id="m-att", sequence=2, accepted=accepted)
    mod._lane_source = lambda redis, wakeup: _FakeSource([prompt, attachment])

    state = {"external_events": [_prompt_accepted()]}
    folded = asyncio.run(mod.fold_turn_external_events(_entrypoint(), state))
    blocks = asyncio.run(seam.materialize_turn_attachments(folded))

    assert len(blocks) == 1
    assert blocks[0]["type"] == "image"
    assert blocks[0]["media_type"] == "image/png"
