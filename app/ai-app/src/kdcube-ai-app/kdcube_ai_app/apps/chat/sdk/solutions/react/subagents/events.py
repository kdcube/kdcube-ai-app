# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Authoring ``subagent.*`` events into a conversation's event lane.

The pipe is the sanctioned inception primitive consent grants ride on: a
``ConversationExternalEvent`` published into the per-conversation lane via
``RedisConversationExternalEventSource.publish``. The transport ``kind`` is
uniformly ``"external_event"``; the semantic type rides nested in
``payload.event.type``. Passive by construction, exactly like the consent
grant: published with ``task_payload=None`` (so the stored task envelope
carries no request to run) and ``reactive: False`` in the nested event (so a
live turn folds it without buying iteration credit) — a subagent event can
never start anything resembling a turn by itself. A LIVE parent turn folds
it through the lane watcher; otherwise it rests in the lane as passive
context the next turn folds in. The react timeline fold renders every folded
event and advances the lane cursor (fold totality), so no ``subagent.*``
type needs bespoke render support.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("kdcube.react.subagents")

SUBAGENT_EVENT_TRANSPORT_KIND = "external_event"
SUBAGENT_EVENT_SOURCE_ID = "react.subagent"
SUBAGENT_CHARTER_EVENT_KIND = "subagent.charter"
SUBAGENT_CONTRIBUTION_EVENT_KIND = "subagent.contribution"
SUBAGENT_CONVERGED_EVENT_KIND = "subagent.converged"
SUBAGENT_FAILED_EVENT_KIND = "subagent.failed"


@dataclass
class ParentLaneAddress:
    """The full lane address a subagent reports back to."""

    tenant: str = ""
    project: str = ""
    user_id: str = ""
    conversation_id: str = ""
    turn_id: str = ""
    agent_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant": self.tenant,
            "project": self.project,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "agent_id": self.agent_id,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "ParentLaneAddress":
        raw = raw if isinstance(raw, dict) else {}
        return cls(
            tenant=str(raw.get("tenant") or ""),
            project=str(raw.get("project") or ""),
            user_id=str(raw.get("user_id") or ""),
            conversation_id=str(raw.get("conversation_id") or ""),
            turn_id=str(raw.get("turn_id") or ""),
            agent_id=str(raw.get("agent_id") or ""),
        )

    @classmethod
    def from_runtime_ctx(cls, runtime_ctx: Any) -> "ParentLaneAddress":
        return cls(
            tenant=str(getattr(runtime_ctx, "tenant", "") or ""),
            project=str(getattr(runtime_ctx, "project", "") or ""),
            user_id=str(getattr(runtime_ctx, "user_id", "") or ""),
            conversation_id=str(getattr(runtime_ctx, "conversation_id", "") or ""),
            turn_id=str(getattr(runtime_ctx, "turn_id", "") or ""),
            agent_id=str(getattr(runtime_ctx, "agent_id", "") or ""),
        )


def build_lane_source(*, redis: Any, address: ParentLaneAddress) -> Any:
    from kdcube_ai_app.apps.chat.external_events import (
        build_conversation_external_event_source,
    )

    return build_conversation_external_event_source(
        redis=redis,
        tenant=address.tenant,
        project=address.project,
        conversation_id=address.conversation_id,
        user_id=address.user_id,
        agent_id=address.agent_id or "main",
    )


def _utc_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


async def publish_subagent_event(
    *,
    lane_source: Any,
    semantic_type: str,
    text: str,
    facts: Optional[Dict[str, Any]] = None,
    author: str = "",
    target_turn_id: Optional[str] = None,
) -> Any:
    """Author one ``subagent.*`` event into ``lane_source``'s conversation.

    ``facts`` is the structured body (child conversation ref, contributed
    refs, charter summary...). It lands both beside the text in the nested
    model-facing event body and at the payload top level for programmatic
    consumers. The published event carries ``task_payload=None`` — passive by
    construction (permanently unpromotable).
    """
    facts = dict(facts or {})
    event_ts = _utc_iso()
    event = await lane_source.publish(
        kind=SUBAGENT_EVENT_TRANSPORT_KIND,
        source=author or SUBAGENT_EVENT_SOURCE_ID,
        event_source_id=SUBAGENT_EVENT_SOURCE_ID,
        text=text,
        target_turn_id=target_turn_id,
        payload={
            "text": text,
            "event": {
                "type": semantic_type,
                "event_source_id": SUBAGENT_EVENT_SOURCE_ID,
                "reactive": False,
                "timestamp": event_ts,
                # The nested payload.event carries the model-facing sentence
                # plus the structured facts; the timeline fold surfaces it as
                # the event block's `ret` body.
                "payload": {
                    "mime": "text/markdown",
                    "event": {
                        "text": text,
                        **facts,
                    },
                },
            },
            **facts,
        },
        # Passive by construction: no task payload means the promoter acks
        # the event; it can never start a turn.
        task_payload=None,
    )
    LOGGER.info(
        "[react.subagents] event authored: conversation=%s type=%s author=%s seq=%s",
        getattr(lane_source, "conversation_id", ""),
        semantic_type,
        author,
        getattr(event, "sequence", None),
    )
    return event


def contribution_refs_for_parent(
    *, refs: List[str], child_conversation_id: str
) -> List[str]:
    """Conversation-qualify the child's logical refs for the parent.

    Bare react refs are turn-qualified (``conv:fi:turn_x...``); resolvers
    treat them as belonging to the CURRENT conversation. Inserting the
    ``conv_<child id>.`` scope segment right after the namespace makes the
    same ref resolvable from the parent conversation (react.pull routes the
    lookup by the embedded conversation id).
    """
    out: List[str] = []
    conv_scope = f"conv_{child_conversation_id}."
    for raw in refs or []:
        ref = str(raw or "").strip()
        if not ref:
            continue
        if ref.startswith("conv:") and conv_scope not in ref:
            ns, _, rest = ref.partition(":")
            kind, _, tail = rest.partition(":")
            if kind and tail and not tail.startswith("conv_"):
                ref = f"{ns}:{kind}:{conv_scope[:-1]}.{tail}"
        out.append(ref)
    return out
