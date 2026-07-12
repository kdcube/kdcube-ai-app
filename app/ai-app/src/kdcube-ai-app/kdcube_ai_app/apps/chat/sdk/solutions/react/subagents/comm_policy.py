# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""The subagent communicator policy — chosen in exactly one place.

A subagent turn runs through the same processor path as any turn, so it
arrives with a real communicator carrying the child conversation's routing.
``build_subagent_child_comm`` is where the child's emission policy is
applied: it returns the communicator the child workflow actually uses.

The current policy is silent: a deny-all event filter stops every emission
at ``ChatCommunicator.emit`` — the single choke point all high-level methods
(delta/step/event/service_event/complete/error) funnel through. The child's
work still persists fully (timeline, workspace, lane events); the filter
governs live emission only. Visibility policy evolves by swapping THIS
builder (e.g. to a stamping pass-through that routes to the parent
conversation's room), never by touching callers.
"""

from __future__ import annotations

from typing import Any, Optional

from kdcube_ai_app.apps.chat.emitters import ChatCommunicator


class DenyAllEventFilter:
    """Every communicator emission is filtered out at ``ChatCommunicator.emit``."""

    def allow_event(self, **_kwargs) -> bool:
        return False


def build_subagent_child_comm(
    base_comm: ChatCommunicator,
    *,
    conversation_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    subagent: Optional[dict] = None,
) -> ChatCommunicator:
    """The child turn's communicator.

    Keeps the transport and service identity of ``base_comm`` (hosting and
    accounting read tenant/project/user from ``comm.service``) and the child
    conversation ids, and applies the subagent emission policy. ``subagent``
    is the envelope stamp the policy may attach to emissions; the silent
    policy accepts and ignores it, keeping the builder signature stable for
    policy swaps.
    """
    del subagent
    conversation = dict(getattr(base_comm, "conversation", None) or {})
    if conversation_id:
        conversation["conversation_id"] = conversation_id
    if turn_id:
        conversation["turn_id"] = turn_id
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
