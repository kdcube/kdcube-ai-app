# SPDX-License-Identifier: MIT

from __future__ import annotations

from types import SimpleNamespace

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.react.v3.agents.decision import (
    parse_react_decision_bundle_from_raw,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.v3.runtime import ReactSolverV2
from kdcube_ai_app.apps.chat.sdk.solutions.react.v3.round import ReactRound


class _LogStub:
    def log(self, *args, **kwargs):
        return None


def _solver_stub() -> ReactSolverV2:
    solver = ReactSolverV2.__new__(ReactSolverV2)
    solver.log = _LogStub()
    solver.ctx_browser = SimpleNamespace(
        runtime_ctx=SimpleNamespace(turn_id="turn-1"),
        timeline=SimpleNamespace(last_external_event_seq=0),
    )
    solver.comm = SimpleNamespace(delta=_noop_async, service_event=_noop_async)
    solver.tools_subsystem = None
    solver.multi_action_mode = "safe_fanout"
    solver._merge_with_pool = _noop_async
    solver._drain_external_events = _noop_async
    solver._apply_steer_interrupt_if_requested = _always_false
    solver._run_cancellable_phase = _run_phase
    return solver


async def _noop_async(*args, **kwargs):
    return None


async def _always_false(*args, **kwargs):
    return False


async def _run_phase(*, phase, coro):
    del phase
    return False, await coro


def test_parse_react_decision_bundle_from_repeated_channels():
    raw = """
<channel:thinking>searching</channel:thinking>
<channel:ReactDecisionOutV2>```json
{"action":"call_tool","notes":"search","tool_call":{"tool_id":"web_tools.web_search","params":{"q":"one"}}}
```</channel:ReactDecisionOutV2>
<channel:ReactDecisionOutV2>```json
{"action":"call_tool","notes":"read","tool_call":{"tool_id":"react.read","params":{"paths":["so:sources_pool[1]"]}}}
```</channel:ReactDecisionOutV2>
"""
    parsed = parse_react_decision_bundle_from_raw(full_raw=raw, json_raw=None)

    assert parsed["candidate_count"] == 2
    assert parsed["errors"] == []
    assert [d["tool_call"]["tool_id"] for d in parsed["decisions"]] == [
        "web_tools.web_search",
        "react.read",
    ]


def test_parse_react_decision_bundle_from_repeated_full_round_sequences():
    raw = """
<channel:thinking>search one</channel:thinking>
<channel:ReactDecisionOutV2>```json
{"action":"call_tool","notes":"search one","tool_call":{"tool_id":"web_tools.web_search","params":{"q":"one"}}}
```</channel:ReactDecisionOutV2>
<channel:code></channel:code>
<channel:thinking>search two</channel:thinking>
<channel:ReactDecisionOutV2>```json
{"action":"call_tool","notes":"search two","tool_call":{"tool_id":"web_tools.web_fetch","params":{"url":"https://example.com"}}}
```</channel:ReactDecisionOutV2>
<channel:code></channel:code>
"""
    parsed = parse_react_decision_bundle_from_raw(full_raw=raw, json_raw=None)

    assert parsed["candidate_count"] == 2
    assert parsed["errors"] == []
    assert [d["tool_call"]["tool_id"] for d in parsed["decisions"]] == [
        "web_tools.web_search",
        "web_tools.web_fetch",
    ]


def test_parse_react_decision_bundle_ignores_literal_channel_mentions_in_thinking():
    raw = """
<channel:thinking>
Explain the literal syntax `<channel:ReactDecisionOutV2>...</channel:ReactDecisionOutV2>` to the user.
</channel:thinking>
<channel:ReactDecisionOutV2>```json
{"action":"call_tool","notes":"search one","tool_call":{"tool_id":"web_tools.web_search","params":{"q":"one"}}}
```</channel:ReactDecisionOutV2>
"""
    parsed = parse_react_decision_bundle_from_raw(full_raw=raw, json_raw=None)

    assert parsed["candidate_count"] == 1
    assert parsed["errors"] == []
    assert [d["tool_call"]["tool_id"] for d in parsed["decisions"]] == [
        "web_tools.web_search",
    ]


def test_parse_react_decision_bundle_from_multiple_fenced_blocks_in_single_channel():
    json_raw = """
```json
{"action":"call_tool","notes":"search","tool_call":{"tool_id":"web_tools.web_search","params":{"q":"one"}}}
```
```json
{"action":"call_tool","notes":"search 2","tool_call":{"tool_id":"web_tools.web_fetch","params":{"url":"https://example.com"}}}
```
"""
    parsed = parse_react_decision_bundle_from_raw(full_raw=None, json_raw=json_raw)

    assert parsed["candidate_count"] == 2
    assert parsed["errors"] == []
    assert [d["tool_call"]["tool_id"] for d in parsed["decisions"]] == [
        "web_tools.web_search",
        "web_tools.web_fetch",
    ]


@pytest.mark.asyncio
async def test_prepare_safe_multi_action_bundle_accepts_safe_tools():
    solver = _solver_stub()
    bundle = [
        {
            "action": "call_tool",
            "notes": "search",
            "tool_call": {
                "tool_id": "web_tools.web_search",
                "params": {"q": "one"},
            },
        },
        {
            "action": "call_tool",
            "notes": "read",
            "tool_call": {
                "tool_id": "react.read",
                "params": {"paths": ["so:sources_pool[1]"]},
            },
        },
    ]
    accepted, error, extra = await solver._prepare_safe_multi_action_bundle(
        bundle=bundle,
        adapters_by_id={"web_tools.web_search": {}},
    )

    assert error is None
    assert extra is None
    assert [d["tool_call"]["tool_id"] for d in accepted] == [
        "web_tools.web_search",
        "react.read",
    ]


@pytest.mark.asyncio
async def test_prepare_safe_multi_action_bundle_rejects_unsafe_tool():
    solver = _solver_stub()
    bundle = [
        {
            "action": "call_tool",
            "notes": "search",
            "tool_call": {
                "tool_id": "web_tools.web_search",
                "params": {"q": "one"},
            },
        },
        {
            "action": "call_tool",
            "notes": "write",
            "tool_call": {
                "tool_id": "react.write",
                "params": {"path": "files/report.md", "channel": "canvas", "content": "x", "kind": "file"},
            },
        },
    ]
    accepted, error, extra = await solver._prepare_safe_multi_action_bundle(
        bundle=bundle,
        adapters_by_id={"web_tools.web_search": {}},
    )

    assert accepted == []
    assert error == "multi_action_bundle_unsafe_tool"
    assert extra == {"index": 1, "tool_id": "react.write"}


def test_validate_decision_packet_channel_consistency_rejects_multi_action_with_code():
    solver = _solver_stub()
    packet = {
        "channels": {
            "code": {"text": "print('x')"},
        }
    }
    bundle = [
        {
            "action": "call_tool",
            "tool_call": {"tool_id": "web_tools.web_search", "params": {"q": "one"}},
        },
        {
            "action": "call_tool",
            "tool_call": {"tool_id": "react.read", "params": {"paths": ["so:sources_pool[1]"]}},
        },
    ]

    error, extra = solver._validate_decision_packet_channel_consistency(packet=packet, bundle=bundle)

    assert error == "code_channel_with_multi_action"
    assert extra == {"bundle_size": 2}


def test_validate_decision_packet_channel_consistency_allows_single_exec_with_code():
    solver = _solver_stub()
    packet = {
        "channels": {
            "code": {"text": "print('x')"},
        }
    }
    bundle = [
        {
            "action": "call_tool",
            "tool_call": {"tool_id": "exec_tools.execute_code_python", "params": {"contract": [], "prog_name": "x"}},
        },
    ]

    error, extra = solver._validate_decision_packet_channel_consistency(packet=packet, bundle=bundle)

    assert error is None
    assert extra is None


def test_validate_decision_packet_channel_consistency_rejects_non_exec_with_code():
    solver = _solver_stub()
    packet = {
        "channels": {
            "code": {"text": "print('x')"},
        }
    }
    bundle = [
        {
            "action": "call_tool",
            "tool_call": {"tool_id": "web_tools.web_search", "params": {"q": "one"}},
        },
    ]

    error, extra = solver._validate_decision_packet_channel_consistency(packet=packet, bundle=bundle)

    assert error == "code_channel_without_single_exec"
    assert extra == {"action": "call_tool", "tool_id": "web_tools.web_search"}


@pytest.mark.asyncio
async def test_tool_execution_node_runs_pending_bundle_sequentially(monkeypatch):
    solver = _solver_stub()
    executed: list[tuple[str, str]] = []
    noted: list[tuple[str, str]] = []
    merged: list[int] = []

    async def _fake_merge(*, collections, workdir, outdir, record_streamers, timeline_streamer):
        del workdir, outdir, record_streamers, timeline_streamer
        merged.append(len(collections[0]))

    async def _fake_execute(*, react, state):
        del react
        decision = state["last_decision"]
        tool_id = decision["tool_call"]["tool_id"]
        call_id = state.get("pending_tool_call_id") or ""
        executed.append((tool_id, call_id))
        state["pending_sources"] = [{"sid": len(executed)}]
        return state

    def _fake_note(*, ctx_browser, notes, tool_call_id, tool_id, action, iteration):
        del ctx_browser, action, iteration
        noted.append((tool_id, tool_call_id))

    solver._merge_with_pool = _fake_merge
    monkeypatch.setattr(ReactRound, "execute", _fake_execute)
    monkeypatch.setattr(ReactRound, "note", _fake_note)

    state = {
        "workdir": ".",
        "outdir": ".",
        "pending_tool_bundle": [
            {
                "decision": {
                    "action": "call_tool",
                    "notes": "search",
                    "tool_call": {"tool_id": "web_tools.web_search", "params": {"q": "one"}},
                },
                "tool_call_id": "tc_first",
            },
            {
                "decision": {
                    "action": "call_tool",
                    "notes": "read",
                    "tool_call": {"tool_id": "react.read", "params": {"paths": ["so:sources_pool[1]"]}},
                },
                "tool_call_id": "tc_second",
            },
        ],
    }

    out = await solver._tool_execution_node(state)

    assert executed == [
        ("web_tools.web_search", "tc_first"),
        ("react.read", "tc_second"),
    ]
    assert noted == [
        ("web_tools.web_search", "tc_first"),
        ("react.read", "tc_second"),
    ]
    assert merged == [1, 1]
    assert out["pending_tool_call_id"] is None
