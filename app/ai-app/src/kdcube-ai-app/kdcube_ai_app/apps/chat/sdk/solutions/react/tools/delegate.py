# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import json
import traceback
from typing import Any, Dict

from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.charter import (
    DEFAULT_SUBAGENT_MAX_ROUNDS,
    MAX_SUBAGENT_MAX_ROUNDS,
    parse_charter,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.events import ParentLaneAddress
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.fork import (
    build_fork_marker_block,
    build_fork_projection,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.launch import SubagentLaunchRequest
from kdcube_ai_app.apps.chat.sdk.solutions.react.tools.common import (
    add_block,
    notice_block,
    tc_result_path,
    tool_call_block,
)

TOOL_SPEC = {
    "id": "react.delegate",
    "purpose": (
        "Delegate a scoped assignment to a subagent: a full ReAct agent scheduled as "
        "its own turn in its own conversation, in parallel with you. The subagent opens "
        "with a fork of your visible context (this conversation's working summaries "
        "plus your in-progress turn) and your charter as its task; it inherits your "
        "tool and skill configuration. The call returns immediately with the child "
        "conversation ref; a fork marker block records the spawn on your timeline, and "
        "you continue your own work — finish your turn whenever you are done, even with "
        "subagents still running. The subagent's reports arrive on this conversation's "
        "event lane as subagent.contribution events and a final subagent.converged (or "
        "subagent.failed) event; if you have already finished, the final event starts a "
        "follow-up turn that delivers the outcome. Contributed refs are pullable with "
        "react.pull as written. Delegate work that is self-contained and worth its own "
        "budget: a sizable research or drafting assignment you would otherwise "
        "interleave with your main thread. A subagent cannot spawn subagents. Each "
        "subagent round is a full model call billed like yours: prefer one "
        "well-chartered subagent over many small ones, and prefer doing quick work "
        "yourself."
    ),
    "args": {
        "charter": (
            "object (FIRST FIELD). The assignment contract: "
            "{goal: str (required — what the subagent must achieve, self-contained; it "
            "cannot ask you or the user questions), "
            "deliverables: [str] (declared outputs, e.g. files it should produce), "
            f"max_rounds: int (round budget, default {DEFAULT_SUBAGENT_MAX_ROUNDS}, "
            f"max {MAX_SUBAGENT_MAX_ROUNDS}), "
            "contribute: str (what to send back and when, e.g. 'the final report file "
            "ref plus a 5-line summary')}."
        ),
        "model": (
            "str (SECOND FIELD, optional). Model override for the subagent's decision "
            "agent; omit to use the configured subagent default."
        ),
    },
    "returns": (
        "launch ticket {child_conversation_id, child_conversation_ref, child_turn_id, "
        "status} — the subagent runs as its own scheduled turn after this returns"
    ),
}


async def handle_react_delegate(
    *, react: Any = None, ctx_browser: Any, state: Dict[str, Any], tool_call_id: str
) -> Dict[str, Any]:
    last_decision = state.get("last_decision") or {}
    tool_call = last_decision.get("tool_call") or {}
    tool_id = "react.delegate"
    params = tool_call.get("params") or {}
    runtime_ctx = getattr(ctx_browser, "runtime_ctx", None)
    turn_id = str(getattr(runtime_ctx, "turn_id", "") or "")

    tool_call_block(
        ctx_browser=ctx_browser,
        tool_call_id=tool_call_id,
        tool_id=tool_id,
        payload={
            "tool_id": tool_id,
            "tool_call_id": tool_call_id,
            "params": params,
        },
    )

    def _fail(code: str, message: str) -> Dict[str, Any]:
        notice_block(
            ctx_browser=ctx_browser,
            tool_call_id=tool_call_id,
            code=code,
            message=message,
            rel="result",
        )
        payload = {"status": "rejected", "code": code, "message": message}
        add_block(ctx_browser, {
            "turn": turn_id,
            "type": "react.tool.result",
            "call_id": tool_call_id,
            "tool_id": tool_id,
            "mime": "application/json",
            "path": tc_result_path(turn_id=turn_id, call_id=tool_call_id),
            "text": json.dumps(payload, ensure_ascii=False, indent=2),
            "meta": {"tool_call_id": tool_call_id},
        })
        state["last_tool_result"] = payload
        return state

    charter, err = parse_charter(params)
    if charter is None:
        return _fail(
            "delegate_missing_goal",
            "react.delegate requires charter.goal — the subagent's self-contained assignment.",
        )
    depth = int(getattr(runtime_ctx, "subagent_depth", 0) or 0)
    if depth >= 1:
        return _fail(
            "delegate_depth_limit",
            "A subagent completes its own charter; it does not spawn subagents.",
        )
    spawner = getattr(runtime_ctx, "subagent_spawner", None)
    if spawner is None or not hasattr(spawner, "spawn"):
        return _fail(
            "delegate_unavailable",
            "Subagent spawning is not wired for this runtime.",
        )

    parent = ParentLaneAddress.from_runtime_ctx(runtime_ctx)
    try:
        timeline = getattr(ctx_browser, "timeline", None)
        parent_blocks = list(getattr(timeline, "blocks", None) or [])
        current_turn_blocks = list(ctx_browser.current_turn_blocks() or [])
    except Exception:
        parent_blocks = []
        current_turn_blocks = []

    request = SubagentLaunchRequest(
        charter=charter,
        parent=parent,
        fork_blocks=[],  # filled below with the child conversation id unknown yet
        allowed_plugins=list(getattr(react, "_run_allowed_plugins", None) or []) or None,
        allowed_tool_names_by_alias=getattr(react, "_run_allowed_tool_names_by_alias", None),
        parent_depth=depth,
        tool_call_id=tool_call_id,
    )
    # The projection is child-id independent (refs are qualified with the
    # PARENT conversation id), so it is built once here.
    request.fork_blocks = build_fork_projection(
        parent_blocks=parent_blocks,
        parent_current_turn_blocks=current_turn_blocks,
        parent_conversation_id=parent.conversation_id,
        parent_turn_id=parent.turn_id,
        child_conversation_id="",
    )

    try:
        ticket = await spawner.spawn(request)
    except Exception as exc:
        try:
            log = getattr(react, "log", None)
            if log is not None:
                log.log(f"[react.delegate] spawn failed: {traceback.format_exc()}", level="ERROR")
        except Exception:
            pass
        from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.schedule import (
            SubagentEnqueueRejected,
        )

        if isinstance(exc, SubagentEnqueueRejected):
            return _fail(
                "delegate_queue_saturated",
                f"The task queue declined the subagent right now ({exc.reason}). "
                "Continue with your own work and delegate again later if still worthwhile.",
            )
        return _fail("delegate_spawn_failed", f"Subagent spawn failed: {exc}")

    marker = build_fork_marker_block(
        parent_turn_id=parent.turn_id,
        child_conversation_id=ticket.child_conversation_id,
        child_turn_id=ticket.child_turn_id,
        charter_summary=charter.summary_line(),
        deliverables=list(charter.deliverables or []),
        max_rounds=charter.max_rounds,
        tool_call_id=tool_call_id,
    )
    add_block(ctx_browser, marker)

    payload = ticket.to_dict()
    payload["charter"] = charter.to_dict()
    add_block(ctx_browser, {
        "turn": turn_id,
        "type": "react.tool.result",
        "call_id": tool_call_id,
        "tool_id": tool_id,
        "mime": "application/json",
        "path": tc_result_path(turn_id=turn_id, call_id=tool_call_id),
        "text": json.dumps(payload, ensure_ascii=False, indent=2),
        "meta": {"tool_call_id": tool_call_id},
    })
    state["last_tool_result"] = payload
    return state
