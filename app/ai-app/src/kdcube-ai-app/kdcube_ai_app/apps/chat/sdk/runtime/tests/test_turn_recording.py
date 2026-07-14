# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Framework-neutral conversation recording (option A) — module + entrypoint wiring."""

import json

import pytest

from kdcube_ai_app.apps.chat.sdk.infra.economics.policy import EconomicsLimitException
from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint import BaseEntrypoint
from kdcube_ai_app.apps.chat.sdk.runtime.turn_recording import (
    ASSISTANT_COMPLETION_BLOCK_TYPE,
    build_error_turn_log_payload,
    build_minimal_turn_log_payload,
    mark_turn_error_surfaced,
    mark_turn_log_recorded,
    record_conversation_timeline,
    record_error_turn_log_if_absent,
    record_minimal_turn_log_if_absent,
    reset_turn_error_surfaced,
    reset_turn_log_recorded,
    turn_error_was_surfaced,
    turn_log_was_recorded,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.timeline import TIMELINE_KIND


class _FakeConversationClient:
    """Stand-in for ContextRAGClient: records save calls and, like the real
    ``save_turn_log_as_artifact``, marks the turn recorded after writing. Its
    ``recent`` reports back the timeline artifacts written so far (matched by
    kind + conversation), so the register-once timeline logic is exercised."""

    def __init__(self):
        self.calls = []
        self.artifact_calls = []
        self.recent_calls = []

    async def save_turn_log_as_artifact(self, **kwargs):
        self.calls.append(kwargs)
        mark_turn_log_recorded()
        return {"hosted_uri": "u", "message_id": "m", "rn": "r"}

    async def save_artifact(self, **kwargs):
        self.artifact_calls.append(kwargs)
        return {"hosted_uri": "u", "message_id": "m", "rn": "r"}

    async def recent(self, **kwargs):
        self.recent_calls.append(kwargs)
        wanted = set(kwargs.get("kinds") or [])
        conv = kwargs.get("conversation_id")
        limit = kwargs.get("limit")
        # Mirror the real index row: `text` == the artifact's content_str, and rows
        # come back newest-first (most-recent timeline wins).
        items = [
            {"turn_id": a.get("turn_id"), "text": a.get("content_str") or ""}
            for a in reversed(self.artifact_calls)
            if f"artifact:{a.get('kind')}" in wanted
            and (conv is None or a.get("conversation_id") == conv)
        ]
        if isinstance(limit, int):
            items = items[:limit]
        return {"items": items}


# ---------------------------------------------------------------- module unit


@pytest.mark.asyncio
async def test_records_minimal_log_for_non_react_turn():
    reset_turn_log_recorded()
    client = _FakeConversationClient()
    wrote = await record_minimal_turn_log_if_absent(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo",
        agent_id="raw", final_answer="Hello there.",
    )
    assert wrote is True
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["turn_id"] == "turn-1"
    assert call["agent_id"] == "raw"
    blocks = call["payload"]["blocks"]
    completions = [b for b in blocks if b["type"] == ASSISTANT_COMPLETION_BLOCK_TYPE]
    assert len(completions) == 1
    assert completions[0]["text"] == "Hello there."


@pytest.mark.asyncio
async def test_no_double_write_when_turn_log_already_recorded():
    # React path: a rich turn log was written this turn -> flag set -> no-op.
    reset_turn_log_recorded()
    mark_turn_log_recorded()
    client = _FakeConversationClient()
    wrote = await record_minimal_turn_log_if_absent(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo",
        final_answer="Would be written if the flag were unset.",
    )
    assert wrote is False
    assert client.calls == []


@pytest.mark.asyncio
async def test_empty_final_answer_is_not_recorded():
    reset_turn_log_recorded()
    client = _FakeConversationClient()
    for answer in ("", "   ", "\n\t "):
        wrote = await record_minimal_turn_log_if_absent(
            conversation_client=client,
            tenant="t", project="p", user="u", user_type="registered",
            conversation_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo",
            final_answer=answer,
        )
        assert wrote is False
    assert client.calls == []


@pytest.mark.asyncio
async def test_steps_become_assistant_step_blocks():
    reset_turn_log_recorded()
    client = _FakeConversationClient()
    wrote = await record_minimal_turn_log_if_absent(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo",
        final_answer="Done.",
        steps=[
            {"text": "Thinking", "status": "started"},
            {"step": "Working", "status": "running"},
            {"text": "   "},  # dropped: blank
        ],
    )
    assert wrote is True
    blocks = client.calls[0]["payload"]["blocks"]
    steps = [b for b in blocks if b["type"] == "assistant.step"]
    assert [b["text"] for b in steps] == ["Thinking", "Working"]
    assert blocks[-1]["type"] == ASSISTANT_COMPLETION_BLOCK_TYPE


def test_build_minimal_turn_log_payload_shape():
    payload = build_minimal_turn_log_payload(final_answer="Answer", turn_id="turn-9")
    assert payload["blocks_count"] == len(payload["blocks"]) == 1
    assert payload["blocks"][0]["type"] == ASSISTANT_COMPLETION_BLOCK_TYPE
    assert payload["blocks"][0]["turn"] == "turn-9"
    assert "ts" in payload and "end_ts" in payload
    # No title key unless one is supplied (later turns).
    assert "conversation_title" not in payload


def test_build_minimal_turn_log_payload_carries_title():
    payload = build_minimal_turn_log_payload(
        final_answer="Answer", turn_id="turn-9", conversation_title="  Weekend plans  ",
    )
    assert payload["conversation_title"] == "Weekend plans"


# ------------------------------------------------- conversation-title persist
#
# The conversation LIST reads the title from the per-conversation timeline
# artifact (kind conv.timeline.v1), NOT the turn log. The minimal recorder writes
# that artifact on a new conversation so a run-to-completion bundle's turns list
# titled, matching the React path's shape.


@pytest.mark.asyncio
async def test_records_conversation_title_timeline_artifact():
    reset_turn_log_recorded()
    client = _FakeConversationClient()
    wrote = await record_conversation_timeline(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo",
        conversation_title="  Weekend plans  ", agent_id="raw",
    )
    assert wrote is True
    assert len(client.artifact_calls) == 1
    call = client.artifact_calls[0]
    assert call["kind"] == TIMELINE_KIND
    assert call["conversation_id"] == "conv-1"
    # The conversation list json-parses content_str and reads conversation_title.
    parsed = json.loads(call["content_str"])
    assert parsed["conversation_title"] == "Weekend plans"
    # The stored payload also carries it (timeline shape).
    assert call["content"]["conversation_title"] == "Weekend plans"


@pytest.mark.asyncio
async def test_blank_title_still_registers_conversation():
    # No title -> the conversation is still registered (so it lists), title empty.
    client = _FakeConversationClient()
    wrote = await record_conversation_timeline(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo",
        conversation_title="",
    )
    assert wrote is True
    assert len(client.artifact_calls) == 1
    assert client.artifact_calls[0]["kind"] == TIMELINE_KIND
    assert json.loads(client.artifact_calls[0]["content_str"])["conversation_title"] == ""


@pytest.mark.asyncio
async def test_later_blank_turn_carries_title_forward_and_refreshes():
    # A first titled turn registers the conversation; a later title-less turn
    # refreshes the timeline (advancing recency) while carrying the title forward
    # -- never shadowing the title with a blank one.
    client = _FakeConversationClient()
    await record_conversation_timeline(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo",
        conversation_title="Weekend plans", conversation_started_at="2026-07-13T00:00:00Z",
    )
    wrote2 = await record_conversation_timeline(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-2", bundle_id="bundle.demo",
        conversation_title="",
    )
    assert wrote2 is True
    # Two timeline rows now (one per turn); the most recent still carries the title
    # and the original started_at (carried forward).
    assert len(client.artifact_calls) == 2
    latest = json.loads(client.artifact_calls[-1]["content_str"])
    assert latest["conversation_title"] == "Weekend plans"
    assert latest["conversation_started_at"] == "2026-07-13T00:00:00Z"
    assert client.artifact_calls[-1]["turn_id"] == "turn-2"


@pytest.mark.asyncio
async def test_blank_title_no_recent_still_registers():
    # A client without `recent` cannot read a prior timeline, but must still
    # register the conversation so it lists (title-less).
    class _NoRecent:
        def __init__(self):
            self.artifact_calls = []

        async def save_artifact(self, **kwargs):
            self.artifact_calls.append(kwargs)
            return {}

    client = _NoRecent()
    wrote = await record_conversation_timeline(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo",
        conversation_title="",
    )
    assert wrote is True
    assert len(client.artifact_calls) == 1


@pytest.mark.asyncio
async def test_minimal_log_with_title_writes_both_artifacts():
    reset_turn_log_recorded()
    client = _FakeConversationClient()
    wrote = await record_minimal_turn_log_if_absent(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo",
        agent_id="raw", final_answer="Hello.", conversation_title="Weekend plans",
    )
    assert wrote is True
    # turn log written...
    assert len(client.calls) == 1
    assert client.calls[0]["payload"]["conversation_title"] == "Weekend plans"
    # ...AND the conversation-title timeline artifact.
    assert len(client.artifact_calls) == 1
    assert client.artifact_calls[0]["kind"] == TIMELINE_KIND


@pytest.mark.asyncio
async def test_minimal_log_without_title_registers_conversation():
    # A turn with no title still registers the conversation (so it lists); each
    # recorded turn refreshes the timeline (advancing recency, mirroring React).
    reset_turn_log_recorded()
    client = _FakeConversationClient()
    wrote = await record_minimal_turn_log_if_absent(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo",
        agent_id="raw", final_answer="First answer.",
    )
    assert wrote is True
    assert len(client.calls) == 1
    assert "conversation_title" not in client.calls[0]["payload"]
    # The conversation was registered (title-less) so it appears in the list.
    assert len(client.artifact_calls) == 1
    assert client.artifact_calls[0]["kind"] == TIMELINE_KIND
    parsed = json.loads(client.artifact_calls[0]["content_str"])
    assert parsed["conversation_title"] == ""

    # A second no-title turn: turn log written AND the timeline refreshed.
    reset_turn_log_recorded()
    wrote2 = await record_minimal_turn_log_if_absent(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-2", bundle_id="bundle.demo",
        agent_id="raw", final_answer="Second answer.",
    )
    assert wrote2 is True
    assert len(client.calls) == 2
    assert len(client.artifact_calls) == 2
    assert client.artifact_calls[-1]["turn_id"] == "turn-2"


# ------------------------------------------------- entrypoint (BaseEntrypoint)
#
# The fallback lives on the app layer, not the orchestrator: BaseEntrypoint.run()
# resets the flag at turn start and calls _record_turn_log_fallback() after
# execute_core, using its own get_ctx_client(). These tests exercise that method
# directly on a minimal stand-in (only get_ctx_client + logger are used).


class _FakeLogger:
    def __init__(self):
        self.warnings = []

    def log(self, message, level="INFO"):
        if str(level).upper() == "WARNING":
            self.warnings.append(message)


class _FakeEntrypoint:
    """Minimal stand-in exposing only what _record_turn_log_fallback touches."""

    # Bind the real method under test.
    _record_turn_log_fallback = BaseEntrypoint._record_turn_log_fallback

    def __init__(self, client):
        self._client = client
        self.logger = _FakeLogger()

    async def get_ctx_client(self):
        return self._client


def _fallback_kwargs(*, final_answer="Answer.", steps=None):
    return dict(
        result={"final_answer": final_answer, "step_logs": steps or []},
        tenant="tenant-a", project="project-a", user_id="user-1",
        user_type="registered", thread_id="conv-1", turn_id="turn-1",
        bundle_id="bundle.demo", agent_id="raw",
    )


@pytest.mark.asyncio
async def test_entrypoint_records_for_non_react_turn():
    reset_turn_log_recorded()
    client = _FakeConversationClient()
    ep = _FakeEntrypoint(client)
    await ep._record_turn_log_fallback(**_fallback_kwargs(final_answer="Framework-neutral answer."))
    assert len(client.calls) == 1
    assert client.calls[0]["payload"]["blocks"][-1]["text"] == "Framework-neutral answer."
    assert client.calls[0]["agent_id"] == "raw"


@pytest.mark.asyncio
async def test_entrypoint_no_double_write_when_react_already_recorded():
    # React wrote its own rich log this turn -> flag set -> fallback is a no-op.
    reset_turn_log_recorded()
    mark_turn_log_recorded()
    client = _FakeConversationClient()
    ep = _FakeEntrypoint(client)
    await ep._record_turn_log_fallback(**_fallback_kwargs(final_answer="React answer."))
    assert client.calls == []


@pytest.mark.asyncio
async def test_entrypoint_skips_empty_answer():
    reset_turn_log_recorded()
    client = _FakeConversationClient()
    ep = _FakeEntrypoint(client)
    await ep._record_turn_log_fallback(**_fallback_kwargs(final_answer="   "))
    assert client.calls == []


@pytest.mark.asyncio
async def test_entrypoint_no_ctx_client_is_noop():
    reset_turn_log_recorded()
    ep = _FakeEntrypoint(None)  # get_ctx_client() -> None (no pg_pool available)
    await ep._record_turn_log_fallback(**_fallback_kwargs())
    assert ep.logger.warnings == []  # a missing client is not an error


@pytest.mark.asyncio
async def test_entrypoint_recording_failure_never_fails_turn():
    class _BoomClient:
        async def save_turn_log_as_artifact(self, **kwargs):
            raise RuntimeError("store down")

    reset_turn_log_recorded()
    ep = _FakeEntrypoint(_BoomClient())
    # Recording raises internally but is swallowed and logged; no exception escapes.
    await ep._record_turn_log_fallback(**_fallback_kwargs(final_answer="Answer survives."))
    assert ep.logger.warnings, "a recording failure should be logged as a warning"


def test_reset_clears_prior_turn_mark():
    # run() calls reset_turn_log_recorded() at each turn's start; prove the flag
    # scoping the fallback depends on is reset/mark/reset as expected.
    reset_turn_log_recorded()
    assert turn_log_was_recorded() is False
    mark_turn_log_recorded()
    assert turn_log_was_recorded() is True
    reset_turn_log_recorded()
    assert turn_log_was_recorded() is False


# ------------------------------------------------------- failed-turn recording


def test_build_error_turn_log_payload_marks_error():
    payload = build_error_turn_log_payload(
        error_message="bind_tools not implemented", turn_id="turn-e", error_type="NotImplementedError",
    )
    assert payload["blocks_count"] == len(payload["blocks"]) == 1
    block = payload["blocks"][0]
    assert block["type"] == ASSISTANT_COMPLETION_BLOCK_TYPE
    assert block["text"] == "bind_tools not implemented"
    assert block["meta"] == {"error": True, "error_type": "NotImplementedError"}


def test_build_error_turn_log_payload_defaults_blank_message():
    payload = build_error_turn_log_payload(error_message="   ", turn_id="turn-e")
    assert payload["blocks"][0]["text"] == "An error occurred."


@pytest.mark.asyncio
async def test_records_error_log_for_crashed_turn():
    reset_turn_log_recorded()
    client = _FakeConversationClient()
    wrote = await record_error_turn_log_if_absent(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo",
        agent_id="raw", error_message="boom", error_type="RuntimeError",
    )
    assert wrote is True
    block = client.calls[0]["payload"]["blocks"][-1]
    assert block["text"] == "boom"
    assert block["meta"]["error"] is True


@pytest.mark.asyncio
async def test_error_log_no_double_write_when_already_recorded():
    reset_turn_log_recorded()
    mark_turn_log_recorded()
    client = _FakeConversationClient()
    wrote = await record_error_turn_log_if_absent(
        conversation_client=client,
        tenant="t", project="p", user="u", user_type="registered",
        conversation_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo",
        error_message="boom",
    )
    assert wrote is False
    assert client.calls == []


def test_error_surfaced_flag_reset_mark():
    reset_turn_error_surfaced()
    assert turn_error_was_surfaced() is False
    mark_turn_error_surfaced()
    assert turn_error_was_surfaced() is True
    reset_turn_error_surfaced()
    assert turn_error_was_surfaced() is False


# ----------------------------------------- _surface_turn_failure (backstop)


class _CaptureComm:
    def __init__(self):
        self.error_calls = []
        self.step_calls = []

    async def error(self, **kwargs):
        self.error_calls.append(kwargs)

    async def step(self, **kwargs):
        self.step_calls.append(kwargs)


class _FailureEntrypoint:
    """Stand-in binding the real backstop methods over minimal collaborators."""

    _surface_turn_failure = BaseEntrypoint._surface_turn_failure
    _record_failed_turn_log = BaseEntrypoint._record_failed_turn_log
    report_turn_error = BaseEntrypoint.report_turn_error

    def __init__(self, client):
        self._client = client
        self.logger = _FakeLogger()
        self._comm = _CaptureComm()
        self.comm_context = None

    @property
    def comm(self):
        return self._comm

    async def get_ctx_client(self):
        return self._client


def _failure_kwargs():
    return dict(
        tenant="t", project="p", user_id="u1", user_type="registered",
        thread_id="conv-1", turn_id="turn-1", bundle_id="bundle.demo", agent_id="raw",
    )


@pytest.mark.asyncio
async def test_surface_turn_failure_emits_and_records():
    reset_turn_log_recorded()
    reset_turn_error_surfaced()
    client = _FakeConversationClient()
    ep = _FailureEntrypoint(client)
    state = {}
    await ep._surface_turn_failure(state=state, exc=RuntimeError("boom"), **_failure_kwargs())
    # client saw a user-visible chat.error
    assert ep._comm.error_calls and ep._comm.error_calls[0]["message"] == "boom"
    # a FAILED turn log was recorded (error-marked)
    assert len(client.calls) == 1
    assert client.calls[0]["payload"]["blocks"][-1]["meta"]["error"] is True
    # the per-turn flag is set so a second backstop pass is inert
    assert turn_error_was_surfaced() is True


@pytest.mark.asyncio
async def test_surface_turn_failure_inert_when_already_surfaced():
    # React path: the workflow already emitted its chat.error + rolled the turn
    # back and marked the flag -> the backstop must not double-emit or re-record.
    reset_turn_log_recorded()
    reset_turn_error_surfaced()
    mark_turn_error_surfaced()
    client = _FakeConversationClient()
    ep = _FailureEntrypoint(client)
    await ep._surface_turn_failure(state={}, exc=RuntimeError("boom"), **_failure_kwargs())
    assert ep._comm.error_calls == []
    assert client.calls == []


@pytest.mark.asyncio
async def test_surface_turn_failure_skips_economics_limit():
    reset_turn_log_recorded()
    reset_turn_error_surfaced()
    client = _FakeConversationClient()
    ep = _FailureEntrypoint(client)
    await ep._surface_turn_failure(
        state={}, exc=EconomicsLimitException("rate", code="rate"), **_failure_kwargs()
    )
    assert ep._comm.error_calls == []
    assert client.calls == []
    assert turn_error_was_surfaced() is False
