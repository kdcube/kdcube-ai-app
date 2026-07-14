# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""Per-turn economics survives a conversation reload — the run-to-completion seam.

A turn's cost ($ badge) and elapsed time show LIVE while the turn streams: the
economics door emits `accounting.usage` (cost) and this app emits
`chat.turn.summary` (time). Both ride the turn's recorded comm. But a
run-to-completion app writes no React timeline, so unless the recorded events are
PERSISTED, a reloaded turn shows neither — the cost and time were gone after
reload.

The React/workspace path persists them via `_save_events_artifact` in its
`post_run_hook`: the recorded events become the `conv.artifacts.events` artifact
the conversation reload replays (`ctx_rag` lists `artifact:conv.artifacts.events`
among the UI artifacts it re-surfaces per turn). This app now does exactly the
same — the SAME shared SDK mechanism, no hand-rolled economics format.

These tests exercise that seam offline: recording on, emit the cost + timing
events on the turn's comm, run `post_run_hook`, and assert the saved
`conv.artifacts.events` artifact carries BOTH the cost (`cost_total_usd`) and the
elapsed time (`elapsed_ms`) — the fields the reload reader replays — scoped to the
economics/record user.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def _entrypoint_module():
    _n, module = load_dynamic_module_for_path(BUNDLE_ROOT / "entrypoint.py")
    return module


class _Relay:
    """Minimal relay capturing emitted envelopes (ChatCommunicator.emitter)."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def emit(self, *, event, data, **kwargs) -> None:
        self.events.append((event, data))


def _make_comm(relay: _Relay):
    from kdcube_ai_app.apps.chat.emitters import ChatCommunicator

    return ChatCommunicator(
        emitter=relay,
        tenant="t",
        project="p",
        user_id="u1",
        user_type="registered",
        service={"request_id": "r1", "tenant": "t", "project": "p", "user": "u1"},
        conversation={"session_id": "s1", "conversation_id": "conv-1", "turn_id": "turn-1"},
    )


class _FakeCtxClient:
    """Captures `save_artifact` calls (stands in for ContextRAGClient)."""

    def __init__(self) -> None:
        self.saved: list[dict] = []

    async def save_artifact(self, **kwargs) -> None:
        self.saved.append(kwargs)


def _make_entrypoint(comm, ctx_client):
    from kdcube_ai_app.infra.service_hub.inventory import Config as InvConfig

    ep_mod = _entrypoint_module()
    inst = ep_mod.LGPortedAgentsBundle(config=InvConfig(), pg_pool=None, redis=None)
    inst._comm = comm  # the property returns this bound comm

    async def _get_ctx_client():
        return ctx_client

    inst.get_ctx_client = _get_ctx_client
    return inst


def test_reload_events_artifact_carries_cost_and_time() -> None:
    async def _go():
        relay = _Relay()
        comm = _make_comm(relay)
        ctx = _FakeCtxClient()
        inst = _make_entrypoint(comm, ctx)

        # Turn start: the base pre_run_hook enables recording of the persisted
        # event types (accounting.usage, chat.turn.summary).
        inst._start_persist_events_recording()

        # The economics door emits the cost badge live (accounting.usage)...
        await comm.event(
            agent="lg-solution", type="accounting.usage", route="chat.step",
            step="accounting", title="Turn Cost", status="completed",
            data={"cost_total_usd": 0.0123, "weighted_tokens": 456},
        )
        # ...and this app emits the turn's elapsed time (chat.turn.summary).
        await inst._emit_turn_timing(started_ms=1000, total_ms=4200)

        # End of turn: persist the recorded events for reload. state carries the
        # user on the authority projection (raw `user` empty), like a real turn.
        state = {
            "tenant": "t", "project": "p",
            "economics_user": "u1", "authority_user": "u1",
            "conversation_id": "conv-1", "turn_id": "turn-1", "agent_id": "lg-solution",
        }
        await inst.post_run_hook(state=state, result={})
        return ctx

    ctx = asyncio.run(_go())

    # Exactly one conv.artifacts.events artifact was saved for the reload path.
    assert len(ctx.saved) == 1
    art = ctx.saved[0]
    assert art["kind"] == "conv.artifacts.events"
    # Scoped to the economics/record user (raw `user` was empty -> threaded from
    # the authority projection).
    assert art["user_id"] == "u1"
    assert art["conversation_id"] == "conv-1"
    assert art["turn_id"] == "turn-1"

    items = (art.get("content") or {}).get("items") or []
    by_type = {}
    for it in items:
        by_type.setdefault(it.get("type"), []).append(it)

    # The cost badge survives -> reload restores the $ amount.
    acct = by_type.get("accounting.usage") or []
    assert acct, "accounting.usage (cost) not persisted for reload"
    assert acct[0]["data"]["cost_total_usd"] == 0.0123

    # The turn time survives -> reload restores the elapsed time.
    summary = by_type.get("chat.turn.summary") or []
    assert summary, "chat.turn.summary (elapsed time) not persisted for reload"
    assert summary[0]["data"]["elapsed_ms"] == 4200


def test_emit_turn_timing_emits_summary_event() -> None:
    async def _go():
        relay = _Relay()
        comm = _make_comm(relay)
        ctx = _FakeCtxClient()
        inst = _make_entrypoint(comm, ctx)
        await inst._emit_turn_timing(started_ms=500, total_ms=1234)
        return relay

    relay = asyncio.run(_go())
    summaries = [env for _sock, env in relay.events if env.get("type") == "chat.turn.summary"]
    assert len(summaries) == 1
    env = summaries[0]
    assert env["event"]["step"] == "turn.summary"
    assert env["event"]["status"] == "completed"
    assert env["data"]["elapsed_ms"] == 1234


def test_post_run_hook_without_ctx_client_is_noop() -> None:
    # No conversation client (offline / no pg_pool): persistence is skipped without
    # error — a turn never fails because its events could not be persisted.
    async def _go():
        relay = _Relay()
        comm = _make_comm(relay)
        inst = _make_entrypoint(comm, ctx_client=None)
        inst._start_persist_events_recording()
        await inst._emit_turn_timing(started_ms=0, total_ms=10)
        state = {
            "tenant": "t", "project": "p", "economics_user": "u1",
            "conversation_id": "conv-1", "turn_id": "turn-1", "agent_id": "lg-solution",
        }
        # Must not raise.
        await inst.post_run_hook(state=state, result={})

    asyncio.run(_go())
