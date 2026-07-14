# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Framework-neutral conversation recording (option A).

The chat component's conversation list / fetch / reload reads the per-turn
``artifact:turn.log`` — materialized into a ``chat:assistant`` record from an
``assistant.completion`` block. The React workflow writes a rich turn log at
``finish_turn``; a bundle that serves turns with **any other framework**
(LangGraph, LangChain, raw calls) via ``execute_core`` writes none, so its
turns stream live but leave no fetchable record.

This module makes conversation persistence framework-agnostic: after any turn,
if no turn log was written, record a **minimal** one carrying the assistant's
final answer (and, optionally, its progress steps). The user message is not
recorded here — it is persisted at ingress independent of the agent, and the
turn-log materializer skips user blocks anyway.

Idempotency is a context flag, not a store query: whoever writes a turn log
(React, or this module) marks it recorded for the current turn; the platform
fallback records the minimal log only when the flag is unset. Reset the flag
at turn start.
"""

from __future__ import annotations

import datetime as _dt
import json
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Sequence

# The block type the turn-log materializer turns into a ``chat:assistant`` row
# (see ctx_rag ``materialize_turn``). Kept as the single source of truth here.
ASSISTANT_COMPLETION_BLOCK_TYPE = "assistant.completion"

# Per-turn "a turn log was written" flag. Set by any turn-log writer; checked by
# the platform fallback. Reset at turn start.
_TURN_LOG_RECORDED: ContextVar[bool] = ContextVar("kdcube_turn_log_recorded", default=False)

# Per-turn "this turn's failure was already surfaced to the client" flag. Set by
# whoever emits a user-visible turn error and owns the failed turn's fate (the
# React/BaseWorkflow error handler emits its chat.error and rolls the turn back).
# Checked by the platform's run() backstop so it never double-emits or re-records
# a failure a framework already handled — it only fires for a turn that raised
# raw (e.g. a non-React execute_core). Reset at turn start.
_TURN_ERROR_SURFACED: ContextVar[bool] = ContextVar("kdcube_turn_error_surfaced", default=False)


def reset_turn_log_recorded() -> None:
    """Call at turn start (before the bundle handles the turn)."""
    _TURN_LOG_RECORDED.set(False)


def mark_turn_log_recorded() -> None:
    """Call from any code path that persists a turn log for the current turn."""
    _TURN_LOG_RECORDED.set(True)


def turn_log_was_recorded() -> bool:
    return bool(_TURN_LOG_RECORDED.get())


def reset_turn_error_surfaced() -> None:
    """Call at turn start (before the bundle handles the turn)."""
    _TURN_ERROR_SURFACED.set(False)


def mark_turn_error_surfaced() -> None:
    """Call from any code path that surfaces a turn failure to the client and
    owns the failed turn's outcome (emit + rollback/record)."""
    _TURN_ERROR_SURFACED.set(True)


def turn_error_was_surfaced() -> bool:
    return bool(_TURN_ERROR_SURFACED.get())


def _utc_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def build_minimal_turn_log_payload(
    *,
    final_answer: str,
    turn_id: str,
    steps: Optional[Sequence[Dict[str, Any]]] = None,
    ts: Optional[str] = None,
    conversation_title: Optional[str] = None,
) -> Dict[str, Any]:
    """The smallest valid turn-log payload: an ``assistant.completion`` block
    carrying the final answer, plus any progress-step blocks the agent chose to
    record. Shape matches what ``ctx_rag.save_turn_log_as_artifact`` expects
    (``V2TurnLog.from_dict``): ``{ts, blocks, blocks_count}``.

    ``conversation_title`` (first turn only) is carried on the payload for symmetry
    with the React turn log; the conversation LIST reads the title from the
    per-conversation timeline artifact, not the turn log — see
    :func:`record_conversation_timeline`.
    """
    now = ts or _utc_iso()
    blocks: List[Dict[str, Any]] = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        text = str(step.get("text") or step.get("step") or "").strip()
        if not text:
            continue
        blocks.append({
            "type": "assistant.step",
            "turn": turn_id,
            "text": text,
            "ts": str(step.get("ts") or now),
            "meta": {"status": str(step.get("status") or "")},
        })
    blocks.append({
        "type": ASSISTANT_COMPLETION_BLOCK_TYPE,
        "turn": turn_id,
        "text": str(final_answer or ""),
        "ts": now,
        "meta": {},
    })
    payload: Dict[str, Any] = {"ts": now, "end_ts": now, "blocks": blocks, "blocks_count": len(blocks)}
    title = str(conversation_title or "").strip()
    if title:
        payload["conversation_title"] = title
    return payload


def build_error_turn_log_payload(
    *,
    error_message: str,
    turn_id: str,
    error_type: Optional[str] = None,
    steps: Optional[Sequence[Dict[str, Any]]] = None,
    ts: Optional[str] = None,
) -> Dict[str, Any]:
    """A minimal turn-log payload for a **failed** turn: an ``assistant.completion``
    block carrying the error text (so the conversation saves and reloads as an
    errored turn), marked ``meta.error`` so the client can render it distinctly.
    Same shape as :func:`build_minimal_turn_log_payload`.
    """
    now = ts or _utc_iso()
    text = str(error_message or "").strip() or "An error occurred."
    blocks: List[Dict[str, Any]] = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        step_text = str(step.get("text") or step.get("step") or "").strip()
        if not step_text:
            continue
        blocks.append({
            "type": "assistant.step",
            "turn": turn_id,
            "text": step_text,
            "ts": str(step.get("ts") or now),
            "meta": {"status": str(step.get("status") or "")},
        })
    blocks.append({
        "type": ASSISTANT_COMPLETION_BLOCK_TYPE,
        "turn": turn_id,
        "text": text,
        "ts": now,
        "meta": {"error": True, "error_type": str(error_type or "")},
    })
    return {"ts": now, "end_ts": now, "blocks": blocks, "blocks_count": len(blocks)}


async def record_error_turn_log_if_absent(
    *,
    conversation_client: Any,
    tenant: str,
    project: str,
    user: str,
    user_type: str,
    conversation_id: str,
    turn_id: str,
    bundle_id: str,
    error_message: str,
    agent_id: Optional[str] = None,
    error_type: Optional[str] = None,
    steps: Optional[Sequence[Dict[str, Any]]] = None,
) -> bool:
    """Record a minimal **failed** turn log when none was written this turn.

    Mirror of :func:`record_minimal_turn_log_if_absent` for the failure path: it
    persists the error as an ``assistant.completion`` block (marked ``error``) so
    the conversation is saved and reloads as an errored turn. No-op when a turn
    log was already recorded this turn. Returns whether it wrote.
    """
    if turn_log_was_recorded():
        return False
    save = getattr(conversation_client, "save_turn_log_as_artifact", None)
    if not callable(save):
        return False
    payload = build_error_turn_log_payload(
        error_message=error_message, turn_id=turn_id, error_type=error_type, steps=steps,
    )
    await save(
        tenant=tenant, project=project, user=user,
        conversation_id=conversation_id, user_type=user_type,
        turn_id=turn_id, bundle_id=bundle_id, agent_id=agent_id,
        payload=payload,
    )
    mark_turn_log_recorded()
    return True


async def _latest_conversation_timeline(
    *,
    conversation_client: Any,
    user: str,
    conversation_id: str,
    bundle_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """The most-recent ``conv.timeline.v1`` index metadata for (user, conv), or
    ``None`` when there is none / it can't be read.

    Returns the parsed compact index text (``conversation_title``,
    ``conversation_started_at``, ...) so a later turn can carry the title +
    started_at forward when it refreshes the timeline (mirroring the React
    timeline, which persists the whole timeline — title included — every turn).
    """
    recent = getattr(conversation_client, "recent", None)
    if not callable(recent):
        return None
    from kdcube_ai_app.apps.chat.sdk.solutions.react.timeline import TIMELINE_KIND
    try:
        res = await recent(
            kinds=[f"artifact:{TIMELINE_KIND}"],
            roles=("artifact",),
            limit=1,
            days=3650,
            user_id=user,
            conversation_id=conversation_id,
            bundle_id=bundle_id,
        )
    except Exception:
        return None
    items = list((res or {}).get("items") or [])
    if not items:
        return None
    try:
        return json.loads(items[0].get("text") or "") or {}
    except Exception:
        # A timeline exists but its index text didn't parse — treat as present
        # (empty metadata) so the caller still refreshes without clobbering intent.
        return {}


async def record_conversation_timeline(
    *,
    conversation_client: Any,
    tenant: str,
    project: str,
    user: str,
    user_type: str,
    conversation_id: str,
    turn_id: str,
    bundle_id: str,
    conversation_title: str = "",
    conversation_started_at: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> bool:
    """Register / refresh a conversation on the conversation list for this turn.

    The chat component's conversation LIST is built from the per-conversation
    ``conv.timeline.v1`` artifact (``ctx_rag.list_conversations`` reads ONLY that
    artifact's index text — never the turn log), the title comes from the same
    artifact (key ``conversation_title``), and the list sorts by its
    ``last_activity_at``. The React workflow persists that artifact every turn from
    its timeline, so a React conversation always lists and floats up on activity. A
    bundle that serves turns without the React timeline (LangGraph, LangChain, raw
    calls) writes none, so its conversations would never list — even after
    recording a turn log. This writes the minimal timeline artifact those readers
    parse, once per recorded turn, so a run-to-completion conversation lists exactly
    like a React one.

    Title / started_at are carried forward: a first turn supplies the generated
    title; a later turn (or a first turn whose title generation failed) supplies
    none, so the prior timeline's title + started_at are re-read and re-persisted —
    the refresh advances ``last_activity_at`` without ever shadowing an earlier
    title with a blank one.

    Reuses the React timeline primitives (the single source of truth for the
    artifact kind + payload shape). No-op on a client without ``save_artifact``.
    Returns whether it wrote.
    """
    save = getattr(conversation_client, "save_artifact", None)
    if not callable(save):
        return False
    title = str(conversation_title or "").strip()
    started_at = str(conversation_started_at or "").strip()
    # Carry the title + started_at forward from any existing timeline so a later,
    # title-less turn refreshes recency without dropping the title.
    prior = await _latest_conversation_timeline(
        conversation_client=conversation_client,
        user=user, conversation_id=conversation_id, bundle_id=bundle_id,
    )
    if prior is None:
        # No existing timeline. If this turn also carries no title, we can't read
        # one back — but we must still register the conversation so it lists, so
        # write a (title-less) timeline now; a later titled turn upgrades it.
        prior = {}
    if not title:
        title = str(prior.get("conversation_title") or "").strip()
    if not started_at:
        started_at = str(prior.get("conversation_started_at") or "").strip() or _utc_iso()
    # Reuse the React timeline primitives (the single source of truth for the
    # artifact kind + payload shape) rather than re-deriving the schema here.
    from kdcube_ai_app.apps.chat.sdk.solutions.react.timeline import (
        TIMELINE_KIND,
        build_timeline_payload,
    )
    payload = build_timeline_payload(
        blocks=[],
        conversation_title=title,
        conversation_started_at=started_at,
        include_sources_pool=True,
    )
    # The index text is what the conversation list/detail json-parse; keep it
    # compact (mirrors the React timeline's own compact index text). The title key
    # is present-but-empty when untitled — the list simply omits the title then.
    content_str = json.dumps(
        {
            "conversation_title": title,
            "conversation_started_at": started_at,
            "last_activity_at": payload.get("last_activity_at") or _utc_iso(),
            "blocks_count": 0,
            "sources_pool_count": 0,
            "turn_ids": [turn_id] if turn_id else [],
        },
        ensure_ascii=False,
    )
    await save(
        kind=TIMELINE_KIND,
        tenant=tenant, project=project, user_id=user,
        conversation_id=conversation_id, user_type=user_type,
        turn_id=turn_id, bundle_id=bundle_id, agent_id=agent_id,
        content=payload, content_str=content_str,
        extra_tags=[f"turn:{turn_id}"] if turn_id else None,
    )
    return True


async def record_minimal_turn_log_if_absent(
    *,
    conversation_client: Any,
    tenant: str,
    project: str,
    user: str,
    user_type: str,
    conversation_id: str,
    turn_id: str,
    bundle_id: str,
    final_answer: str,
    agent_id: Optional[str] = None,
    steps: Optional[Sequence[Dict[str, Any]]] = None,
    conversation_title: Optional[str] = None,
) -> bool:
    """Record the minimal turn log when none was written this turn.

    No-op when a turn log was already recorded (React path) or there is no
    final answer to record. Returns whether it wrote. ``conversation_client`` is
    the platform's ``ContextRAGClient`` (has ``save_turn_log_as_artifact``);
    the caller owns it (the processor / turn lifecycle), not the bundle.

    Every recorded turn also registers/refreshes the conversation on the
    conversation list via :func:`record_conversation_timeline` — the list is built
    ONLY from the ``conv.timeline.v1`` artifact, so without this a run-to-completion
    conversation records its turn log yet never appears in the list. The title
    (first turn) rides on that same registration when present; a later turn (or a
    first turn whose title generation failed) carries the prior title forward while
    advancing recency. Best-effort: a registration failure never undoes the
    recorded answer.
    """
    if turn_log_was_recorded():
        return False
    answer = str(final_answer or "").strip()
    if not answer:
        return False
    save = getattr(conversation_client, "save_turn_log_as_artifact", None)
    if not callable(save):
        return False
    payload = build_minimal_turn_log_payload(
        final_answer=answer, turn_id=turn_id, steps=steps,
        conversation_title=conversation_title,
    )
    await save(
        tenant=tenant, project=project, user=user,
        conversation_id=conversation_id, user_type=user_type,
        turn_id=turn_id, bundle_id=bundle_id, agent_id=agent_id,
        payload=payload,
    )
    mark_turn_log_recorded()
    try:
        await record_conversation_timeline(
            conversation_client=conversation_client,
            tenant=tenant, project=project, user=user, user_type=user_type,
            conversation_id=conversation_id, turn_id=turn_id, bundle_id=bundle_id,
            conversation_title=conversation_title or "", agent_id=agent_id,
        )
    except Exception:
        # The answer is already recorded; a registration failure is non-fatal.
        pass
    return True
