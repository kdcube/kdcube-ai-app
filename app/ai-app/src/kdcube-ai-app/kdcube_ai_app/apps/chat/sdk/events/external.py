# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from kdcube_ai_app.apps.chat.sdk.event_identity import DEFAULT_REACT_AGENT_ID, normalize_agent_id


@dataclass(frozen=True)
class EventTimelineIdentityCard:
    """Identity of one ordered event lane and its timeline mutation scope."""

    tenant: str
    project: str
    user_id: str
    conversation_id: str
    agent_id: str = DEFAULT_REACT_AGENT_ID
    bundle_id: str = ""
    user_type: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "agent_id", normalize_agent_id(self.agent_id))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant": self.tenant,
            "project": self.project,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "agent_id": self.agent_id,
            "bundle_id": self.bundle_id,
            "user_type": self.user_type,
        }


@dataclass
class ExternalEventMaterializationCtx:
    """Runtime mechanisms supplied to an offline event materializer."""

    event_source: Any
    ctx_client: Any = None
    critical_section: Any = None
    logger: Any = None
    settings: Any = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalEventMaterializationResult:
    """Result returned by `@process_offline_events`."""

    materialized_count: int = 0
    last_sequence: Optional[int] = None
    last_event_id: str = ""
    reactive_event_pending: bool = False
    handoff_event_id: str = ""
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "materialized_count": int(self.materialized_count or 0),
            "last_sequence": self.last_sequence,
            "last_event_id": self.last_event_id,
            "reactive_event_pending": bool(self.reactive_event_pending),
            "handoff_event_id": self.handoff_event_id,
            "reason": self.reason,
        }
