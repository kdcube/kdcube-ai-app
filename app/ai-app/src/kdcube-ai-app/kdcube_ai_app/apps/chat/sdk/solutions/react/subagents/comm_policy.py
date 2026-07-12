# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""The subagent communicator policy — chosen in exactly one place.

A subagent turn runs through the same processor path as any turn, so it
arrives with a real communicator carrying the child conversation's routing.
``build_subagent_child_comm`` is where the child's emission policy is
applied: it returns the communicator the child workflow actually uses.

Two visibilities exist, selected by the agent's
``react.agents.<id>.subagents.visibility`` config (default ``silent``):

- ``silent`` — a deny-all event filter stops every emission at
  ``ChatCommunicator.emit``, the single choke point all high-level methods
  (delta/step/event/service_event/complete/error) funnel through. The
  child's work still persists fully (timeline, workspace, lane events); the
  filter governs live emission only.
- ``thread`` — a stamping pass-through: every emission is delivered to the
  PARENT conversation's room (the user's existing socket; the relay carries
  it from whatever proc the child landed on) while the event identity stays
  the CHILD's (``conversation.conversation_id``/``turn_id``), and each
  envelope gains a top-level ``subagent`` stamp so clients multiplex the
  child's stream into a collapsible thread anchored at the fork turn.

Visibility policy evolves by extending THIS builder, never by touching
callers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from kdcube_ai_app.apps.chat.emitters import ChatCommunicator

LOGGER = logging.getLogger("kdcube.react.subagents")

SUBAGENT_VISIBILITY_SILENT = "silent"
SUBAGENT_VISIBILITY_THREAD = "thread"


def normalize_subagent_visibility(raw: Any) -> str:
    """The visibility knob's vocabulary: ``silent`` (default) or ``thread``."""
    text = str(raw or "").strip().lower()
    if text == SUBAGENT_VISIBILITY_THREAD:
        return SUBAGENT_VISIBILITY_THREAD
    return SUBAGENT_VISIBILITY_SILENT


class DenyAllEventFilter:
    """Every communicator emission is filtered out at ``ChatCommunicator.emit``."""

    def allow_event(self, **_kwargs) -> bool:
        return False


@dataclass
class SubagentThreadComm(ChatCommunicator):
    """Thread-visibility communicator: stamp every emission at the choke point.

    ``subagent_stamp`` is attached as the envelope's top-level ``subagent``
    key on EVERY emission (start/step/delta/event/service/complete/error),
    so clients anchor the child's stream without parsing text. Delivery
    routing (room/session channel) is the parent conversation's — set by
    :func:`build_subagent_child_comm` — while ``conversation.conversation_id``
    and ``turn_id`` stay the child's.
    """

    subagent_stamp: Dict[str, Any] = field(default_factory=dict)

    async def emit(self, event: str, data: dict, broadcast: bool = False):
        if isinstance(data, dict) and self.subagent_stamp:
            data = {**data, "subagent": dict(self.subagent_stamp)}
        return await super().emit(event, data, broadcast)


def build_subagent_child_comm(
    base_comm: ChatCommunicator,
    *,
    conversation_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    subagent: Optional[dict] = None,
    visibility: Optional[str] = None,
    parent_session_id: Optional[str] = None,
) -> ChatCommunicator:
    """The child turn's communicator.

    Keeps the transport and service identity of ``base_comm`` (hosting and
    accounting read tenant/project/user from ``comm.service``) and the child
    conversation ids, and applies the subagent emission policy.

    ``visibility`` selects the policy (``silent`` default). ``subagent`` is
    the envelope stamp
    (``{child_conversation_id, forked_from_conversation_id,
    forked_from_turn_id, charter_goal}``) the thread policy attaches to
    every emission; ``parent_session_id`` is the parent conversation's
    session — the room the user's socket actually joined — and is the thread
    policy's delivery address. Thread mode without a parent session has no
    deliverable room and falls back to silent.
    """
    conversation = dict(getattr(base_comm, "conversation", None) or {})
    if conversation_id:
        conversation["conversation_id"] = conversation_id
    if turn_id:
        conversation["turn_id"] = turn_id

    mode = normalize_subagent_visibility(visibility)
    if mode == SUBAGENT_VISIBILITY_THREAD:
        parent_room = str(parent_session_id or "").strip()
        if parent_room:
            # Delivery is the parent's session channel (conversation.session_id
            # drives the relay's channel derivation AND names the receiving
            # session truthfully); event identity stays the child's.
            conversation["session_id"] = parent_room
            return SubagentThreadComm(
                emitter=base_comm.emitter,
                tenant=base_comm.tenant,
                project=base_comm.project,
                user_id=base_comm.user_id,
                user_type=base_comm.user_type,
                service=dict(base_comm.service or {}),
                conversation=conversation,
                room=parent_room,
                target_sid=None,
                subagent_stamp=dict(subagent or {}),
            )
        LOGGER.warning(
            "[react.subagents] thread visibility without a parent session id; "
            "child conversation=%s runs silent",
            conversation.get("conversation_id"),
        )

    return ChatCommunicator(
        emitter=base_comm.emitter,
        tenant=base_comm.tenant,
        project=base_comm.project,
        user_id=base_comm.user_id,
        user_type=base_comm.user_type,
        service=dict(base_comm.service or {}),
        conversation=conversation,
        room=None,
        target_sid=None,
        event_filter=DenyAllEventFilter(),
    )
