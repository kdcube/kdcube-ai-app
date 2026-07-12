# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Subagent spend attribution for the usage surfaces.

Child spend books under the CHILD conversation/turn (its own fair-scheduled
turn settles its own economics). These helpers keep that spend attributable
on the PARENT's usage views:

- a child turn's ``accounting.usage`` event carries the parent backref
  (:func:`subagent_usage_metadata`), so per-turn/per-conversation views can
  roll it up under the parent turn while keeping it distinguishable as
  helper spend;
- a parent continuation turn (promoted from ``subagent.converged``/
  ``failed``) knows exactly which helper turns completed
  (:func:`completed_helper_refs`), so its own usage event can present
  "turn total X, of which helpers Y" (:func:`build_helpers_block`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.child_turn import (
    charter_turn_context,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.events import (
    SUBAGENT_CONVERGED_EVENT_KIND,
    SUBAGENT_FAILED_EVENT_KIND,
)

_COMPLETION_KINDS = {SUBAGENT_CONVERGED_EVENT_KIND, SUBAGENT_FAILED_EVENT_KIND}


def subagent_usage_metadata(payload: Any) -> Optional[Dict[str, Any]]:
    """The helper-spend marker for a subagent child turn's usage events.

    ``None`` for every non-charter turn. The backref keys the rollup into
    the parent turn; ``helper: true`` keeps the row distinguishable."""
    context = charter_turn_context(payload)
    if context is None:
        return None
    return {
        "helper": True,
        "subagent": {
            "parent_conversation_id": context.parent.conversation_id,
            "parent_turn_id": context.parent.turn_id,
            "charter_goal": context.charter.summary_line(),
        },
    }


def _payload_external_events(payload: Any) -> List[Dict[str, Any]]:
    request = getattr(payload, "request", None)
    if request is None and isinstance(payload, dict):
        request = payload.get("request")
    events = getattr(request, "external_events", None)
    if events is None and isinstance(request, dict):
        events = request.get("external_events")
    return [e for e in (events or []) if isinstance(e, dict)]


def completed_helper_refs(payload: Any) -> List[Dict[str, Any]]:
    """The helper turns a continuation payload delivers outcomes for.

    Reads the ``subagent.converged``/``subagent.failed`` bodies from the
    task payload's accepted external events; each ref names the child
    conversation/turn whose spend the parent view rolls up."""
    out: List[Dict[str, Any]] = []
    for event in _payload_external_events(payload):
        if str(event.get("type") or "") not in _COMPLETION_KINDS:
            continue
        body = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        facts = body.get("event") if isinstance(body.get("event"), dict) else {}
        child_conversation_id = str(facts.get("child_conversation_id") or "").strip()
        if not child_conversation_id:
            continue
        out.append({
            "child_conversation_id": child_conversation_id,
            "child_turn_id": str(facts.get("child_turn_id") or "").strip(),
            "charter_goal": str(facts.get("charter_goal") or ""),
            "outcome": (
                "converged"
                if str(event.get("type")) == SUBAGENT_CONVERGED_EVENT_KIND
                else "failed"
            ),
        })
    return out


def build_helpers_block(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The distinguishable helper-spend block for a usage event.

    ``items``: one entry per helper turn, each carrying its refs plus the
    computed ``cost_usd`` / ``weighted_tokens``. Returns ``None`` when there
    is nothing to report."""
    rows = [dict(item) for item in (items or []) if isinstance(item, dict)]
    if not rows:
        return None
    return {
        "cost_total_usd": round(sum(float(r.get("cost_usd") or 0.0) for r in rows), 6),
        "weighted_tokens": int(sum(int(r.get("weighted_tokens") or 0) for r in rows)),
        "count": len(rows),
        "items": rows,
    }
