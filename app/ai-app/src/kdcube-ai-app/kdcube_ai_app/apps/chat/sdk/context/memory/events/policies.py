# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping
from typing import Any

from kdcube_ai_app.apps.chat.sdk.solutions.react.events import block_production_policy


MEMORY_READ_BLOCK_POLICY_ID = "memory.block_production.read_result"


def _ret_mapping(target: Mapping[str, Any]) -> dict[str, Any]:
    ret = target.get("ret")
    if isinstance(ret, Mapping):
        return dict(ret)
    raw = target.get("raw")
    if isinstance(raw, Mapping):
        output = raw.get("output")
        if isinstance(output, Mapping):
            return dict(output)
    return {}


def _memory_ref(payload: Mapping[str, Any]) -> str:
    ref = str(payload.get("memory_ref") or payload.get("object_ref") or payload.get("ref") or "").strip()
    if ref.startswith("mem:"):
        return ref
    memory = payload.get("memory")
    if isinstance(memory, Mapping):
        memory_id = str(memory.get("id") or "").strip()
        if memory_id:
            return f"mem:{memory_id}"
    return ref


def _memory_text(payload: Mapping[str, Any]) -> str:
    memory = payload.get("memory")
    if not isinstance(memory, Mapping):
        return json.dumps(dict(payload), ensure_ascii=False, indent=2, default=str)

    rows = {
        "memory_ref": _memory_ref(payload),
        "id": memory.get("id"),
        "memory": memory.get("memory"),
        "context": memory.get("context"),
        "kind": memory.get("kind"),
        "status": memory.get("status"),
        "labels": memory.get("labels") or [],
        "keywords": memory.get("keywords") or [],
        "tier": memory.get("tier"),
        "updated_at": memory.get("updated_at"),
    }
    events = payload.get("events")
    if isinstance(events, list):
        rows["events"] = events
    return json.dumps(
        {key: value for key, value in rows.items() if value not in (None, "", [])},
        ensure_ascii=False,
        indent=2,
        default=str,
    )


@block_production_policy(
    event_policy_id=MEMORY_READ_BLOCK_POLICY_ID,
    description="Render memory.read_memory as a memory-owned mem:<id> fact block.",
)
def memory_read_block_policy(
    target: MutableMapping[str, Any],
    **_: Any,
) -> MutableMapping[str, Any]:
    if not isinstance(target, MutableMapping):
        return target
    payload = _ret_mapping(target)
    tool_id = str(target.get("tool_id") or target.get("event_source_id") or "memory.read_memory").strip()
    tool_call_id = str(target.get("tool_call_id") or target.get("event_id") or "").strip()
    turn_id = str(target.get("turn_id") or "").strip()
    path = _memory_ref(payload)
    if not path:
        final_params = target.get("final_params") if isinstance(target.get("final_params"), Mapping) else {}
        path = str(final_params.get("memory_ref") or final_params.get("path") or "").strip()
    blocks = target.setdefault("blocks", [])
    if isinstance(blocks, list):
        blocks.append({
            "turn": turn_id,
            "type": "react.tool.result",
            "call_id": tool_call_id,
            "tool_id": tool_id,
            "event_source_id": tool_id,
            "mime": "application/json",
            "path": path,
            "text": _memory_text(payload),
            "meta": {
                "tool_call_id": tool_call_id,
                "tool_id": tool_id,
                "event_source_id": tool_id,
                "memory_ref": path,
                "render_as": "memory.read",
            },
        })
    target["blocks_produced"] = True
    target["result_items"] = []
    target["result_items_produced"] = True
    target["declared_file_items"] = []
    target["declared_file_items_produced"] = True
    return target


__all__ = [
    "MEMORY_READ_BLOCK_POLICY_ID",
    "memory_read_block_policy",
]
