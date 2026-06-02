# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

# chat/protocol.py
from __future__ import annotations
from typing import Any, Dict, Optional, Literal, List
from datetime import datetime
from pydantic import BaseModel, Field

from kdcube_ai_app.apps.chat.sdk.event_identity import DEFAULT_REACT_AGENT_ID


# -----------------------------
# History / client-side request
# -----------------------------

class ChatHistoryMessage(BaseModel):
    role: str = Field(default="user")
    content: str
    timestamp: Optional[str] = None

def _iso_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


class _ProtoBase(BaseModel):
    """Base that exposes `.dump_model()` as requested (alias of model_dump)."""
    def dump_model(self) -> Dict[str, Any]:
        return self.model_dump()


class ServiceCtx(_ProtoBase):
    request_id: str
    tenant: Optional[str] = None
    project: Optional[str] = None
    user: Optional[str] = None
    user_obj: Optional[ExternalEventUser] = None


class ConversationCtx(_ProtoBase):
    session_id: str
    conversation_id: str
    turn_id: str|None = None


class EventCtx(_ProtoBase):
    agent: Optional[str] = None
    step: str
    status: Literal["started", "running", "completed", "error", "skipped"]
    title: Optional[str] = None


class DeltaPart(_ProtoBase):
    text: str
    marker: str = "answer"
    index: int = 0


class ChatEnvelope(_ProtoBase):
    """
    Unified protocol envelope used everywhere on the server and sent to the client as-is.
    """
    type: Literal["chat.start", "chat.step", "chat.delta", "chat.complete", "chat.error", "chat.service"]
    timestamp: str = Field(default_factory=_iso_now)
    service: ServiceCtx
    conversation: ConversationCtx
    event: EventCtx
    data: Any | None = None          # generic payload from bundles/processors
    delta: Optional[DeltaPart] = None

    @staticmethod
    def start(service: ServiceCtx, conv: ConversationCtx, *, message: str, queue_stats: Dict[str, Any] | None = None) -> "ChatEnvelope":
        return ChatEnvelope(
            type="chat.start",
            service=service,
            conversation=conv,
            event=EventCtx(step="turn", status="started", title="Turn Started", agent="user"),
            data={"message": message, "queue_stats": queue_stats or {}},
        )

    @staticmethod
    def step(service: ServiceCtx, conv: ConversationCtx, *, step: str, status: EventCtx.model_fields["status"].annotation, title: str | None = None, data: Any = None, agent: str | None = None) -> "ChatEnvelope":
        return ChatEnvelope(
            type="chat.step",
            service=service,
            conversation=conv,
            event=EventCtx(step=step, status=status, title=title, agent=agent),
            data=data,
        )

    @staticmethod
    def delta(service: ServiceCtx, conv: ConversationCtx, *, text: str, index: int, marker: DeltaPart.model_fields["marker"].annotation = "answer") -> "ChatEnvelope":
        return ChatEnvelope(
            type="chat.delta",
            service=service,
            conversation=conv,
            event=EventCtx(step="stream", status="running", title="Assistant Delta", agent="assistant"),
            delta=DeltaPart(text=text, index=int(index), marker=marker),
        )

    @staticmethod
    def complete(service: ServiceCtx, conv: ConversationCtx, *, data: Any = None, agent: str | None = "answer_generator") -> "ChatEnvelope":
        return ChatEnvelope(
            type="chat.complete",
            service=service,
            conversation=conv,
            event=EventCtx(step="stream", status="completed", title="Turn Completed", agent=agent),
            data=data or {},
        )

    @staticmethod
    def error(service: ServiceCtx, conv: ConversationCtx, *, error: str, title: str | None = "Workflow Error", step: str = "workflow") -> "ChatEnvelope":
        return ChatEnvelope(
            type="chat.error",
            service=service,
            conversation=conv,
            event=EventCtx(step=step, status="error", title=title, agent=None),
            data={"error": error},
        )


# ---- event payload used between ingress and processor ----

class ExternalEventRequest(_ProtoBase):
    message: Optional[str] = None
    chat_history: List[Dict[str, Any]] = []
    operation: Optional[str] = None
    invocation: Optional[Literal["sync", "async"]] = None
    payload: Any | None = None   # ← generic pass-through to bundle
    request_id: Optional[str] = None


class ExternalEventRouting(_ProtoBase):
    bundle_id: str
    session_id: str
    conversation_id: Optional[str] = None
    turn_id: Optional[str] = None
    socket_id: Optional[str] = None


class ExternalEventActor(_ProtoBase):
    tenant_id: Optional[str] = None
    project_id: Optional[str] = None


class ExternalEventUser(_ProtoBase):
    user_type: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    fingerprint: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
    timezone: Optional[str] = None
    utc_offset_min: Optional[int] = None


class ExternalEventConfig(_ProtoBase):
    values: Dict[str, Any] = {}


class ExternalEventMeta(_ProtoBase):
    task_id: str
    created_at: float
    instance_id: Optional[str] = None


class ExternalEventAccounting(_ProtoBase):
    envelope: Dict[str, Any] = {}   # whatever your accounting layer produces


class ExternalEventContinuation(_ProtoBase):
    kind: Literal["regular", "followup", "steer"] = "regular"
    explicit: bool = False
    active_turn_id: Optional[str] = None
    target_turn_id: Optional[str] = None


class ExternalEvent(_ProtoBase):
    """
    Event occurrence metadata for the processor envelope.

    This section identifies what happened (`kind`), which agent lane owns it,
    which event source/policies describe it, and whether it may wake or extend
    a runtime.
    """

    kind: str = "message"
    agent_id: str = DEFAULT_REACT_AGENT_ID
    event_source_id: Optional[str] = None
    event_id: Optional[str] = None
    sequence: Optional[int] = None
    reactive: Optional[bool] = True
    source: Optional[str] = None
    out_of_turn: bool = False


class ExternalEventPayload(_ProtoBase):
    """
    Top-level transport/processor payload for an accepted event occurrence.

    It is not necessarily chat and not necessarily a task. A user message,
    attachment, followup, steer, authored UI event, webhook event, or background
    work item can all travel as this payload. Chat is one event kind.
    """

    meta: Optional[ExternalEventMeta] = None
    routing: Optional[ExternalEventRouting] = None
    actor: Optional[ExternalEventActor] = None
    user: Optional[ExternalEventUser] = None
    request: Optional[ExternalEventRequest] = None
    config: Optional[ExternalEventConfig] = None
    accounting: Optional[ExternalEventAccounting] = None
    continuation: Optional[ExternalEventContinuation] = None
    event: Optional[ExternalEvent] = None
    bundle_call_context: Dict[str, Any] = Field(default_factory=dict)
