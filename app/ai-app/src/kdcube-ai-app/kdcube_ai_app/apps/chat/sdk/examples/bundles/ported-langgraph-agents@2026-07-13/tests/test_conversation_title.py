# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""First-turn conversation title — the run-to-completion seam.

Like workspace, a NEW conversation gets a short auto-generated name. This bundle
serves turns via `execute_core` (no React timeline / gate), so it reuses the SDK
title utility directly and threads the result through two seams:

  1. EMIT  — the SAME `chat.conversation.title` chat event the React workflow
     emits (asserted here on the comm payload), so the chat component updates the
     conversation header live;
  2. PERSIST — the title is stashed on `state`, which the economics door's
     framework-neutral turn recorder reads to persist onto the conversation
     timeline the conversation list reads.

These tests exercise `_finalize_conversation_title` / `_conversation_is_new`
directly, mocking the model (title generation) and the platform conversation
record: a NEW conversation generates + emits + stashes; a SUBSEQUENT conversation
(a prior turn log exists) does neither. (The full graph dispatch — and that the
answer streams regardless — is covered by test_dispatch.py.)
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.runtime import comm_ctx
from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def _entrypoint_module():
    _n, module = load_dynamic_module_for_path(BUNDLE_ROOT / "entrypoint.py")
    return module


class _EventComm:
    """Captures the emitted chat events."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    async def event(self, **kwargs) -> None:
        self.events.append(kwargs)


class _FakeCtxClient:
    """Stand-in for ContextRAGClient's new-conversation probe."""

    def __init__(self, *, has_prior_turn: bool) -> None:
        self._has_prior_turn = has_prior_turn
        self.recent_calls: list[dict] = []

    async def recent(self, **kwargs):
        self.recent_calls.append(kwargs)
        return {"items": [{"turn_id": "prior"}] if self._has_prior_turn else []}


def _make_entrypoint(monkeypatch, *, title: str, has_prior_turn: bool):
    from kdcube_ai_app.infra.service_hub.inventory import Config as InvConfig

    ep_mod = _entrypoint_module()
    inst = ep_mod.LGPortedAgentsBundle(config=InvConfig(), pg_pool=None, redis=None)
    # A truthy model service so the title path is attempted; the generation itself
    # is mocked below (no real model call).
    inst.models_service = object()

    calls = {"generate": 0}

    async def _fake_generate(_svc, *, user_message, answer=None, **_kw):
        calls["generate"] += 1
        return title

    monkeypatch.setattr(ep_mod, "generate_conversation_title", _fake_generate)

    client = _FakeCtxClient(has_prior_turn=has_prior_turn)

    async def _get_ctx_client():
        return client

    monkeypatch.setattr(inst, "get_ctx_client", _get_ctx_client)
    return ep_mod, inst, calls, client


def _finalize(inst, *, conversation_id: str, question: str, answer: str):
    state = {
        "tenant": "t", "project": "p", "user": "alice",
        "conversation_id": conversation_id, "turn_id": "turn-1",
    }

    async def _go():
        comm = _EventComm()
        comm_ctx.set_comm(comm)
        await inst._finalize_conversation_title(
            state=state, conversation_id=conversation_id, question=question, answer=answer,
        )
        return comm, state

    return asyncio.run(_go())


def test_new_conversation_generates_emits_and_persists_title(monkeypatch) -> None:
    _ep, inst, calls, client = _make_entrypoint(
        monkeypatch, title="Weekend Plans", has_prior_turn=False,
    )
    comm, state = _finalize(
        inst, conversation_id="conv-new",
        question="What should I do this weekend?", answer="Consider a hike.",
    )

    # A title was generated on this (new) conversation...
    assert calls["generate"] == 1
    # ...stashed on state for the framework-neutral recorder to persist...
    assert state["conversation_title"] == "Weekend Plans"
    # ...and emitted as the canonical chat.conversation.title event.
    title_events = [e for e in comm.events if e.get("type") == "chat.conversation.title"]
    assert len(title_events) == 1
    evt = title_events[0]
    assert evt["agent"] == "system"
    assert evt["step"] == "conversation_title"
    assert evt["status"] == "completed"
    assert evt["broadcast"] is True
    assert evt["data"]["title"] == "Weekend Plans"
    assert evt["data"]["conversation_id"] == "conv-new"
    # The new-conversation probe queried the turn-log record for this conversation.
    assert client.recent_calls and client.recent_calls[0]["conversation_id"] == "conv-new"
    assert client.recent_calls[0]["kinds"] == ["artifact:turn.log"]


def test_subsequent_conversation_does_not_generate_or_emit(monkeypatch) -> None:
    _ep, inst, calls, client = _make_entrypoint(
        monkeypatch, title="Would Not Be Used", has_prior_turn=True,
    )
    comm, state = _finalize(
        inst, conversation_id="conv-existing",
        question="Another question", answer="Another answer.",
    )

    # A prior turn log exists -> not a new conversation -> no title work.
    assert calls["generate"] == 0
    assert "conversation_title" not in state
    assert [e for e in comm.events if e.get("type") == "chat.conversation.title"] == []


def test_blank_generated_title_is_a_noop(monkeypatch) -> None:
    _ep, inst, calls, client = _make_entrypoint(
        monkeypatch, title="   ", has_prior_turn=False,
    )
    comm, state = _finalize(
        inst, conversation_id="conv-blank", question="Hello there", answer="Hi!",
    )

    # Generation was attempted (new conversation) but produced nothing usable.
    assert calls["generate"] == 1
    assert "conversation_title" not in state
    assert [e for e in comm.events if e.get("type") == "chat.conversation.title"] == []


def test_probe_uses_economics_user_when_raw_actor_keys_absent(monkeypatch) -> None:
    # The economics door records the turn log under state["economics_user"] (the
    # projected-authority record user), which can be set while the raw
    # actor_user/user/fingerprint keys are empty. The new-conversation probe must
    # read that same user, else it falls into the empty-user fail-safe (-> "not
    # new" -> no title). Here only economics_user is present.
    _ep, inst, calls, client = _make_entrypoint(
        monkeypatch, title="Weekend Plans", has_prior_turn=False,
    )
    state = {
        "tenant": "t", "project": "p",
        "economics_user": "02e53484-real-user",
        "conversation_id": "conv-econ", "turn_id": "turn-1",
    }

    async def _go():
        comm = _EventComm()
        comm_ctx.set_comm(comm)
        await inst._finalize_conversation_title(
            state=state, conversation_id="conv-econ",
            question="What should I do this weekend?", answer="Consider a hike.",
        )
        return comm

    comm = asyncio.run(_go())

    # The probe ran under the economics/record user, found no prior turn -> new.
    assert client.recent_calls and client.recent_calls[0]["user_id"] == "02e53484-real-user"
    assert client.recent_calls[0]["conversation_id"] == "conv-econ"
    # A title was generated, stashed, and emitted.
    assert calls["generate"] == 1
    assert state["conversation_title"] == "Weekend Plans"
    assert [e for e in comm.events if e.get("type") == "chat.conversation.title"]


def test_no_answer_still_titles_from_question(monkeypatch) -> None:
    # The title runs BEFORE the agent, from the QUESTION alone, so a missing answer
    # does NOT skip it — this is what lets the title appear even when the turn later
    # errors (e.g. a tool loop hitting the recursion limit).
    _ep, inst, calls, client = _make_entrypoint(
        monkeypatch, title="Km To Miles", has_prior_turn=False,
    )
    comm, state = _finalize(inst, conversation_id="c", question="what is 4.5 km in miles?", answer="   ")
    # Generated + stashed + emitted from the question, with no answer.
    assert calls["generate"] == 1
    assert client.recent_calls and client.recent_calls[0]["conversation_id"] == "c"
    assert state["conversation_title"] == "Km To Miles"
    assert [e for e in comm.events if e.get("type") == "chat.conversation.title"]


def test_blank_question_skips_title(monkeypatch) -> None:
    # With neither a question nor an answer there is nothing to title from: no work,
    # no probe.
    _ep, inst, calls, client = _make_entrypoint(
        monkeypatch, title="Unused", has_prior_turn=False,
    )
    comm, state = _finalize(inst, conversation_id="c", question="   ", answer="   ")
    assert calls["generate"] == 0
    assert client.recent_calls == []
    assert "conversation_title" not in state


# --------------------------------------------------------------------------
# End-to-end (unmocked generation): the FULL title chain offline.
#
# The tests above mock `generate_conversation_title`, so they never exercise the
# model-service seam — the very link that was untested and suspected in the
# "title stays Untitled" report. These drive the REAL utility through a faithful
# model-service stub that mirrors how `stream_with_channels` calls the service
# (`get_client` -> `describe_client` -> `stream_model_text_tracked` streaming the
# two-channel `<channel:thinking>..</channel:thinking><channel:output>{json}
# </channel:output>` protocol). Proves that, given a protocol-compliant model, the
# chain generates -> stashes -> emits the real `chat.conversation.title` event;
# and that a model whose output the channel parser yields no title from (e.g. bare
# JSON without the `<channel:output>` wrapper) fails OPEN to silence — the
# runtime-only failure mode the kept diagnostic logs pinpoint on a live run.
# --------------------------------------------------------------------------

_TITLE_PROTOCOL = (
    "<channel:thinking>Naming this chat.</channel:thinking>"
    "<channel:output>{\"conversation_title\": \"Weekend Hike Plans\"}</channel:output>"
)


class _FaithfulModelService:
    """Faithful `ModelServiceBase` stand-in: drives the exact `get_client` ->
    `describe_client` -> `stream_model_text_tracked` sequence `stream_with_channels`
    uses, streaming a canned model body over `on_delta`/`on_complete`."""

    def __init__(self, body: str) -> None:
        self._body = body

    def get_client(self, role, temperature: float = 0.7):
        return {"role": role}

    def describe_client(self, client, role=None):
        from kdcube_ai_app.infra.service_hub.inventory import ClientConfigHint
        return ClientConfigHint(provider="anthropic", model_name="test-model")

    async def stream_model_text_tracked(
        self, client, messages, *, on_delta, on_complete,
        temperature=0.2, max_tokens=128, client_cfg=None, debug=False,
        role=None, debug_citations=False, **_kw,
    ):
        full = self._body
        mid = len(full) // 2
        await on_delta(full[:mid])
        await on_delta(full[mid:])
        await on_complete(None)
        return {"text": full, "service_error": None, "usage": {}, "model_name": "test-model"}


def _make_entrypoint_with_service(*, body: str, has_prior_turn: bool):
    from kdcube_ai_app.infra.service_hub.inventory import Config as InvConfig

    ep_mod = _entrypoint_module()
    inst = ep_mod.LGPortedAgentsBundle(config=InvConfig(), pg_pool=None, redis=None)
    inst.models_service = _FaithfulModelService(body)
    client = _FakeCtxClient(has_prior_turn=has_prior_turn)

    async def _get_ctx_client():
        return client

    inst.get_ctx_client = _get_ctx_client
    return inst, client


def test_end_to_end_compliant_model_generates_and_emits(monkeypatch) -> None:
    # A protocol-compliant model: the real utility parses the `<channel:output>`
    # JSON, stashes the title on state, and emits the canonical event.
    inst, client = _make_entrypoint_with_service(body=_TITLE_PROTOCOL, has_prior_turn=False)
    comm, state = _finalize(
        inst, conversation_id="conv-e2e",
        question="What should I do this weekend?", answer="",
    )
    assert state["conversation_title"] == "Weekend Hike Plans"
    title_events = [e for e in comm.events if e.get("type") == "chat.conversation.title"]
    assert len(title_events) == 1
    assert title_events[0]["step"] == "conversation_title"
    assert title_events[0]["data"]["title"] == "Weekend Hike Plans"
    assert client.recent_calls and client.recent_calls[0]["conversation_id"] == "conv-e2e"


def test_end_to_end_non_channel_output_fails_open_to_silence(monkeypatch) -> None:
    # A model that emits the title JSON WITHOUT the `<channel:output>` wrapper: the
    # two-channel parser recovers no title, so the chain fails OPEN (no stash, no
    # emit). This is the runtime-only "empty title" branch the kept logs surface;
    # it never raises or blocks the turn.
    inst, _client = _make_entrypoint_with_service(
        body="{\"conversation_title\": \"Bare Json Title\"}", has_prior_turn=False,
    )
    comm, state = _finalize(
        inst, conversation_id="conv-bare", question="Hello there", answer="",
    )
    assert "conversation_title" not in state
    assert [e for e in comm.events if e.get("type") == "chat.conversation.title"] == []


def test_end_to_end_subsequent_conversation_skips_generation(monkeypatch) -> None:
    # A prior turn log exists: the real chain never calls the model at all.
    inst, client = _make_entrypoint_with_service(body=_TITLE_PROTOCOL, has_prior_turn=True)
    comm, state = _finalize(
        inst, conversation_id="conv-existing", question="Another question", answer="",
    )
    assert "conversation_title" not in state
    assert [e for e in comm.events if e.get("type") == "chat.conversation.title"] == []
