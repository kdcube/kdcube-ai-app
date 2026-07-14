# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Reactive-event door: framework-neutral turn recording + failure surfacing.

Two gaps in BaseEntrypointWithEconomics.run() (the economics reactive-event door,
which does not call super().run()), exercised through the real run() with the
economics harness from the characterization suite:

  * Fix B — a run-to-completion turn records a minimal turn log (so a non-React
    execute_core leaves a fetchable conversation record on reload).
  * Fix C — a crashed turn surfaces a user-visible chat.error and records a FAILED
    turn log (so it saves + reloads as an error turn) instead of silently
    "completing"; the lane finalize still runs in the ``finally``. A turn that
    already surfaced its own failure (React marks the per-turn flag) is left
    untouched — no double emit, no re-record.
"""

from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.chatbot import entrypoint_with_economic as econ_mod
from kdcube_ai_app.apps.chat.sdk.runtime.turn_recording import mark_turn_error_surfaced

# Reuse the economics harness (recording fakes + real run() wiring).
from kdcube_ai_app.apps.chat.sdk.infra.economics.tests.test_run_economics_characterization import _make_ep


class _FakeConversationClient:
    def __init__(self):
        self.calls = []

    async def save_turn_log_as_artifact(self, **kwargs):
        self.calls.append(kwargs)
        return {"hosted_uri": "u", "message_id": "m", "rn": "r"}


class _RichComm:
    """Records both service_event (economics telemetry) and error/step/delta
    (turn-failure surfacing)."""

    def __init__(self):
        self.events = []
        self.error_calls = []
        self.step_calls = []
        self.delta_calls = []

    async def service_event(self, **kw):
        self.events.append(kw)

    async def error(self, **kw):
        self.error_calls.append(kw)

    async def step(self, **kw):
        self.step_calls.append(kw)

    async def delta(self, **kw):
        self.delta_calls.append(kw)


def _with_ctx_client(ep, client):
    async def _get_ctx_client():
        return client
    ep.get_ctx_client = _get_ctx_client
    return ep


# ------------------------------------------------------------------- Fix B


@pytest.mark.asyncio
async def test_completed_turn_records_turn_log(monkeypatch):
    ep = _make_ep(role="registered", monkeypatch=monkeypatch)

    async def _execute_core(*, state, thread_id, params):
        return {"final_answer": "Hi there.", "answer": "Hi there."}

    ep.execute_core = _execute_core
    client = _FakeConversationClient()
    _with_ctx_client(ep, client)

    await ep.run()

    assert len(client.calls) == 1, "the completed turn should record one turn log"
    call = client.calls[0]
    assert call["turn_id"] == "turn_char_1"
    assert call["conversation_id"] == "conv1"
    assert call["bundle_id"] == "test-bundle@1"
    assert call["agent_id"], "agent_id must be resolved"
    completion = call["payload"]["blocks"][-1]
    assert completion["text"] == "Hi there."
    assert completion["meta"] == {}  # success, not an error turn


@pytest.mark.asyncio
async def test_completed_turn_without_answer_records_nothing(monkeypatch):
    # No final answer -> nothing to persist (fallback is a no-op, like the base).
    ep = _make_ep(role="registered", monkeypatch=monkeypatch)

    async def _execute_core(*, state, thread_id, params):
        return {"answer": "ok"}  # no final_answer

    ep.execute_core = _execute_core
    client = _FakeConversationClient()
    _with_ctx_client(ep, client)

    await ep.run()
    assert client.calls == []


# ------------------------------------------------------------------- Fix C


@pytest.mark.asyncio
async def test_crashed_turn_surfaces_error_records_failed_log_and_finalizes(monkeypatch):
    finalize_calls = []

    async def _finalize(**kwargs):
        finalize_calls.append(kwargs)

    monkeypatch.setattr(econ_mod, "finalize_reactive_event_lane", _finalize)

    ep = _make_ep(role="registered", monkeypatch=monkeypatch)
    comm = _RichComm()
    ep._comm = comm

    async def _execute_core(*, state, thread_id, params):
        raise RuntimeError("bind_tools boom")

    ep.execute_core = _execute_core
    client = _FakeConversationClient()
    _with_ctx_client(ep, client)

    with pytest.raises(RuntimeError, match="bind_tools boom"):
        await ep.run()

    # (1) client-visible error emitted
    assert comm.error_calls, "a crashed turn must surface a chat.error"
    assert comm.error_calls[0]["message"] == "bind_tools boom"
    # (2) a FAILED turn log recorded (error-marked, reloadable)
    assert len(client.calls) == 1
    completion = client.calls[0]["payload"]["blocks"][-1]
    assert completion["text"] == "bind_tools boom"
    assert completion["meta"]["error"] is True
    assert completion["meta"]["error_type"] == "RuntimeError"
    # (3) the lane finalize still ran in the finally
    assert finalize_calls, "finalize_reactive_event_lane must run in finally"


@pytest.mark.asyncio
async def test_react_surfaced_failure_is_not_double_emitted(monkeypatch):
    # A turn that surfaced its own failure (React emits its chat.error + rolls
    # back, marking the per-turn flag) must pass through untouched.
    finalize_calls = []

    async def _finalize(**kwargs):
        finalize_calls.append(kwargs)

    monkeypatch.setattr(econ_mod, "finalize_reactive_event_lane", _finalize)

    ep = _make_ep(role="registered", monkeypatch=monkeypatch)
    comm = _RichComm()
    ep._comm = comm

    async def _execute_core(*, state, thread_id, params):
        # Simulate the React/BaseWorkflow error handler: it surfaced + handled
        # the failure and marked the flag before re-raising.
        mark_turn_error_surfaced()
        raise RuntimeError("react already surfaced")

    ep.execute_core = _execute_core
    client = _FakeConversationClient()
    _with_ctx_client(ep, client)

    with pytest.raises(RuntimeError, match="react already surfaced"):
        await ep.run()

    assert comm.error_calls == [], "backstop must not double-emit React's error"
    assert client.calls == [], "backstop must not re-record a rolled-back turn"
    assert finalize_calls, "finalize still runs in finally"
