# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from kdcube_ai_app.apps.chat.sdk.runtime.tool_traits import (
    executes_parallel_on_tool_call_complete,
    execution_policy,
    normalize_tool_traits,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.call import get_react_tools_catalog
from kdcube_ai_app.apps.chat.sdk.solutions.react.layout import build_tools_block
from kdcube_ai_app.apps.chat.sdk.solutions.react.round import ReactRound
from kdcube_ai_app.apps.chat.sdk.solutions.react.v3.action_overseer import RoundActionOverseer
from kdcube_ai_app.apps.chat.sdk.solutions.react.v3.early_tool_execution import (
    EarlyToolExecutionListener,
    consumed_early_tool_record,
    drain_early_tool_executions,
    early_tool_execution_identity,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.v3.runtime import ReactSolverV2
from kdcube_ai_app.apps.chat.sdk.solutions.widgets.canvas import TimelineStreamer


def _delegate_decision(charter: str = "Research the topic") -> dict:
    return {
        "action": "call_tool",
        "notes": "Delegate research.",
        "tool_call": {
            "tool_id": "react.delegate",
            "params": {"charter": charter, "agent_alias": "strong_agent"},
        },
    }


def _write_decision() -> dict:
    return {
        "action": "call_tool",
        "notes": "Write the dashboard.",
        "tool_call": {
            "tool_id": "react.write",
            "params": {
                "path": "turn-1/files/dashboard.html",
                "channel": "canvas",
                "content": "<html></html>",
                "kind": "file",
            },
        },
    }


def _listener(*, state: dict, calls: list, action_index: int = 0, protocol_ok: bool = True):
    async def execute_tool(decision: dict, tool_call_id: str):
        calls.append((decision["tool_call"]["params"]["charter"], tool_call_id))
        return {"status": "scheduled", "child_conversation_id": "sub-1"}

    return EarlyToolExecutionListener(
        state=state,
        turn_id="turn-1",
        iteration=2,
        action_index=action_index,
        validate_decision=lambda decision: None,
        validate_protocol=lambda tool_call: {"ok": protocol_ok, "violations": []},
        action_accepted=lambda index, action, tool_id: True,
        execution_policy_allows=lambda decision: True,
        execute_tool=execute_tool,
        execution_tasks={},
    )


def test_delegate_declares_generic_parallel_execution_policy():
    delegate = next(
        item for item in get_react_tools_catalog(subagent_role="parent")
        if item.get("id") == "react.delegate"
    )

    assert delegate["tool_traits"]["strategy"] == ["neutral"]
    assert executes_parallel_on_tool_call_complete(delegate["tool_traits"]) is True
    rendered = build_tools_block([delegate], header="[TOOLS]")
    assert "trigger=tool_call_complete" in rendered
    assert "concurrency=parallel_with_generation" in rendered


def test_execution_policy_preserves_extension_fields():
    traits = normalize_tool_traits({
        "strategy": ["neutral"],
        "execution": {
            "trigger": "TOOL_CALL_COMPLETE",
            "concurrency": "PARALLEL_WITH_GENERATION",
            "result_dependency": "DETACHED",
            "replay": "AT_MOST_ONCE_PER_ROUND",
            "queue": "provider_owned",
        },
    })

    assert executes_parallel_on_tool_call_complete(traits) is True
    assert execution_policy(traits)["queue"] == "provider_owned"


def test_runtime_requires_neutral_strategy_for_parallel_generation_overlap():
    solver = ReactSolverV2.__new__(ReactSolverV2)
    execution = {
        "trigger": "tool_call_complete",
        "concurrency": "parallel_with_generation",
        "result_dependency": "detached",
        "replay": "at_most_once_per_round",
    }

    assert solver._tool_executes_early("react.delegate", adapters_by_id={}) is True
    assert solver._tool_executes_early(
        "tools.safe",
        adapters_by_id={
            "tools.safe": {"tool_traits": {"strategy": ["neutral"], "execution": execution}},
        },
    ) is True
    assert solver._tool_executes_early(
        "tools.write",
        adapters_by_id={
            "tools.write": {"tool_traits": {"strategy": ["exploitation"], "execution": execution}},
        },
    ) is False


def test_early_tool_identity_is_stable_per_round_action_slot():
    first = early_tool_execution_identity(
        turn_id="turn-1",
        iteration=3,
        action_index=0,
        decision=_delegate_decision("A"),
    )
    retry_changed_payload = early_tool_execution_identity(
        turn_id="turn-1",
        iteration=3,
        action_index=0,
        decision=_delegate_decision("B"),
    )
    next_slot = early_tool_execution_identity(
        turn_id="turn-1",
        iteration=3,
        action_index=1,
        decision=_delegate_decision("A"),
    )

    assert retry_changed_payload.action_key == first.action_key
    assert retry_changed_payload.tool_call_id == first.tool_call_id
    assert retry_changed_payload.semantic_fingerprint != first.semantic_fingerprint
    assert next_slot.action_key != first.action_key


@pytest.mark.asyncio
async def test_listener_executes_at_action_completion_and_deduplicates_retry():
    state: dict = {}
    calls: list = []
    listener = _listener(state=state, calls=calls)

    first = await listener.on_action_completed(decision=_delegate_decision("A"))
    retried = await listener.on_action_completed(decision=_delegate_decision("B"))

    assert first is retried
    assert len(calls) == 1
    assert first["status"] == "consumed"
    assert state["last_tool_result"]["child_conversation_id"] == "sub-1"


@pytest.mark.asyncio
async def test_listener_deduplicates_same_call_reordered_by_provider_retry():
    state: dict = {}
    calls: list = []
    decision = _delegate_decision("A")
    first_listener = _listener(state=state, calls=calls, action_index=0)
    second_listener = _listener(state=state, calls=calls, action_index=1)

    first = await first_listener.on_action_completed(decision=decision)
    second = await second_listener.on_action_completed(decision=decision)

    assert first is second
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_listener_waits_for_valid_protocol_before_execution():
    state: dict = {}
    calls: list = []
    listener = _listener(state=state, calls=calls, protocol_ok=False)

    record = await listener.on_action_completed(decision=_delegate_decision())

    assert record is None
    assert calls == []
    identity = early_tool_execution_identity(
        turn_id="turn-1",
        iteration=2,
        action_index=0,
        decision=_delegate_decision(),
    )
    assert consumed_early_tool_record(state=state, identity=identity) is None


@pytest.mark.asyncio
async def test_listener_starts_tool_before_later_sibling_finishes():
    state: dict = {}
    events: list[str] = []

    async def execute_tool(decision: dict, tool_call_id: str):
        del decision, tool_call_id
        events.append("tool_started")
        return {"status": "scheduled"}

    listener = EarlyToolExecutionListener(
        state=state,
        turn_id="turn-1",
        iteration=0,
        action_index=0,
        validate_decision=lambda decision: None,
        validate_protocol=lambda tool_call: {"ok": True, "violations": []},
        action_accepted=lambda index, action, tool_id: True,
        execution_policy_allows=lambda decision: True,
        execute_tool=execute_tool,
        execution_tasks={},
    )

    await listener.on_action_completed(decision=_delegate_decision())
    events.append("sibling_stream_completed")

    assert events == ["tool_started", "sibling_stream_completed"]


@pytest.mark.asyncio
async def test_listener_does_not_wait_for_detached_tool_completion():
    state: dict = {}
    started = asyncio.Event()
    release = asyncio.Event()
    tasks: dict = {}

    async def execute_tool(decision: dict, tool_call_id: str):
        del decision, tool_call_id
        started.set()
        await release.wait()
        return {"status": "scheduled"}

    listener = EarlyToolExecutionListener(
        state=state,
        turn_id="turn-1",
        iteration=0,
        action_index=0,
        validate_decision=lambda decision: None,
        validate_protocol=lambda tool_call: {"ok": True, "violations": []},
        action_accepted=lambda index, action, tool_id: True,
        execution_policy_allows=lambda decision: True,
        execute_tool=execute_tool,
        execution_tasks=tasks,
    )

    record = await listener.on_action_completed(decision=_delegate_decision())

    assert started.is_set()
    assert record["status"] == "running"
    release.set()
    await drain_early_tool_executions(tasks)
    assert record["status"] == "consumed"


@pytest.mark.asyncio
async def test_completed_stream_identity_is_overseer_accepted_before_early_execution():
    state: dict = {}
    tasks: dict = {}
    calls: list = []
    decision = _delegate_decision()

    async def emit_delta(**kwargs):
        del kwargs

    delegate_traits = next(
        item["tool_traits"]
        for item in get_react_tools_catalog(subagent_role="parent")
        if item.get("id") == "react.delegate"
    )
    overseer = RoundActionOverseer(resolve_traits=lambda tool_id, tool_params=None: delegate_traits)
    action_gate = overseer.gate_for(action_index=0, emit_delta=emit_delta)
    answer_gate = overseer.gate_for(action_index=0, emit_delta=emit_delta, lane="final_answer")

    async def report_action(action: str, tool_id: str):
        await overseer.observe_action_signal(
            action_index=0,
            action=action,
            tool_id=tool_id,
            action_gate=action_gate,
            answer_gate=answer_gate,
        )

    timeline = TimelineStreamer(
        emit_delta=emit_delta,
        agent="test",
        stream_notes=False,
        stream_final_answer=False,
        stream_plan=False,
        on_action_identity=report_action,
    )

    async def execute_tool(parsed_decision: dict, tool_call_id: str):
        calls.append((parsed_decision, tool_call_id))
        return {"status": "scheduled"}

    listener = EarlyToolExecutionListener(
        state=state,
        turn_id="turn-1",
        iteration=0,
        action_index=0,
        validate_decision=lambda parsed_decision: None,
        validate_protocol=lambda tool_call: {"ok": True, "violations": []},
        action_accepted=lambda index, action, tool_id: any(
            observed.index == index and observed.action == action and observed.tool_id == tool_id
            for observed in overseer.accepted_actions()
        ),
        execution_policy_allows=lambda parsed_decision: True,
        execute_tool=execute_tool,
        execution_tasks=tasks,
    )

    await timeline.feed(json.dumps(decision))
    await timeline.finish()
    record = await listener.on_action_completed(decision=decision)
    await drain_early_tool_executions(tasks)

    assert [observed.tool_id for observed in overseer.accepted_actions()] == ["react.delegate"]
    assert record["status"] == "consumed"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_multi_action_prevalidated_tool_is_not_protocol_validated_twice():
    solver = ReactSolverV2.__new__(ReactSolverV2)
    solver.tools_subsystem = None
    original_validate = solver._validate_tool_call_protocol
    validated_tool_ids: list[str] = []

    def validate(*, tool_call, adapters_by_id):
        validated_tool_ids.append(str((tool_call or {}).get("tool_id") or ""))
        return original_validate(tool_call=tool_call, adapters_by_id=adapters_by_id)

    solver._validate_tool_call_protocol = validate

    accepted, error, _extra = await solver._prepare_safe_multi_action_bundle(
        bundle=[_delegate_decision(), _write_decision()],
        adapters_by_id={},
        prevalidated_action_indices={0},
    )

    assert error is None
    assert [item["tool_call"]["tool_id"] for item in accepted] == [
        "react.delegate",
        "react.write",
    ]
    assert validated_tool_ids == ["react.write"]


@pytest.mark.asyncio
async def test_multi_action_preserves_stream_index_after_rejected_sibling():
    solver = ReactSolverV2.__new__(ReactSolverV2)
    solver.tools_subsystem = None
    accepted_indices: list[int] = []

    accepted, error, _extra = await solver._prepare_safe_multi_action_bundle(
        bundle=[{"action": "unsupported"}, _delegate_decision()],
        adapters_by_id={},
        prevalidated_action_indices={1},
        accepted_action_indices_out=accepted_indices,
    )

    assert error is None
    assert [item["tool_call"]["tool_id"] for item in accepted] == ["react.delegate"]
    assert accepted_indices == [1]


@pytest.mark.asyncio
async def test_post_generation_node_counts_consumed_tool_without_reexecution(monkeypatch):
    state: dict = {"session_log": [], "turn_id": "turn-1"}
    calls: list = []
    listener = _listener(state=state, calls=calls)
    decision = _delegate_decision()
    record = await listener.on_action_completed(decision=decision)

    solver = ReactSolverV2.__new__(ReactSolverV2)
    solver.ctx_browser = None
    solver.log = SimpleNamespace(log=lambda *args, **kwargs: None)

    async def no_interrupt(*args, **kwargs):
        return False

    async def no_events(*args, **kwargs):
        return None

    solver._apply_steer_interrupt_if_requested = no_interrupt
    solver._drain_external_events = no_events

    async def fail_execute(*, react, state):
        del react, state
        raise AssertionError("post-generation path re-executed the consumed tool")

    monkeypatch.setattr(ReactRound, "execute", fail_execute)
    state["pending_tool_bundle"] = [{
        "decision": decision,
        "tool_call_id": record["tool_call_id"],
        "iteration": 2,
        "action_index": 0,
    }]

    result = await solver._tool_execution_node(state)

    assert len(calls) == 1
    assert result["session_log"][-1]["type"] == "early_tool_consumed"
    assert result["session_log"][-1]["tool_id"] == "react.delegate"
