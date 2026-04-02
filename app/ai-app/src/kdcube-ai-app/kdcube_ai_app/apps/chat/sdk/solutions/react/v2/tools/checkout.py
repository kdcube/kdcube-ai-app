# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import asyncio
from typing import Any, Dict

import json

from kdcube_ai_app.apps.chat.sdk.solutions.react.v2.tools.common import (
    add_block,
    notice_block,
    tool_call_block,
    tc_result_path,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.v2.workspace import (
    WORKSPACE_IMPLEMENTATION_GIT,
    get_workspace_implementation,
)


TOOL_SPEC = {
    "id": "react.checkout",
    "purpose": (
        "Switch the current git-backed workspace to a specific historical version id. "
        "Use this when you want the current-turn workspace itself to start from that version, "
        "rather than only materializing a side-by-side historical snapshot with react.pull."
    ),
    "args": {
        "version": "str turn_id to check out into the current turn workspace",
    },
    "returns": (
        "JSON object {checked_out_version, turn_root, version_ref}. "
        "Only available in git workspace mode. "
        "Requires a clean current turn repo."
    ),
}


async def handle_react_checkout(*, ctx_browser: Any, state: Dict[str, Any], tool_call_id: str) -> Dict[str, Any]:
    last_decision = state.get("last_decision") or {}
    tool_call = last_decision.get("tool_call") or {}
    tool_id = "react.checkout"
    params = tool_call.get("params") or {}
    version = str(params.get("version") or "").strip()
    turn_id = str(getattr(getattr(ctx_browser, "runtime_ctx", None), "turn_id", "") or "").strip()

    tool_call_block(
        ctx_browser=ctx_browser,
        tool_call_id=tool_call_id,
        tool_id=tool_id,
        payload={
            "tool_id": tool_id,
            "tool_call_id": tool_call_id,
            "params": tool_call.get("params") or {},
        },
    )

    if get_workspace_implementation(getattr(ctx_browser, "runtime_ctx", None)) != WORKSPACE_IMPLEMENTATION_GIT:
        notice_block(
            ctx_browser=ctx_browser,
            tool_call_id=tool_call_id,
            code="protocol_violation.checkout_requires_git_workspace",
            message="react.checkout is available only in git workspace mode.",
            extra={"tool_id": tool_id},
        )
        state["retry_decision"] = True
        return state

    if not version:
        notice_block(
            ctx_browser=ctx_browser,
            tool_call_id=tool_call_id,
            code="protocol_violation.checkout_missing_version",
            message="react.checkout requires params.version (turn_id).",
            extra={"tool_id": tool_id},
        )
        state["retry_decision"] = True
        return state

    try:
        from kdcube_ai_app.apps.chat.sdk.solutions.react.v2.git_workspace import checkout_current_turn_git_workspace

        result = await asyncio.to_thread(
            checkout_current_turn_git_workspace,
            runtime_ctx=ctx_browser.runtime_ctx,
            outdir=state["outdir"],
            version_id=version,
        )
    except Exception as exc:
        code = "react.checkout.failed"
        message = f"Failed to checkout workspace version {version}."
        if str(exc) == "workspace_checkout_dirty":
            code = "react.checkout.dirty"
            message = (
                "Current turn workspace is dirty. Commit or discard current-turn changes "
                "before switching the whole workspace version."
            )
        notice_block(
            ctx_browser=ctx_browser,
            tool_call_id=tool_call_id,
            code=code,
            message=message,
            extra={"version": version, "error": str(exc)},
        )
        state["retry_decision"] = True
        return state

    add_block(ctx_browser, {
        "turn": turn_id,
        "type": "react.tool.result",
        "call_id": tool_call_id,
        "mime": "application/json",
        "path": tc_result_path(turn_id=turn_id, call_id=tool_call_id),
        "text": json.dumps(result, ensure_ascii=False, indent=2),
        "meta": {
            "tool_call_id": tool_call_id,
        },
    })
    state["last_tool_result"] = result
    return state
