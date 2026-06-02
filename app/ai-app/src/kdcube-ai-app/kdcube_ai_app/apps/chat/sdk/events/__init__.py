# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Event-source declarations and discovery for chat SDK runtimes."""

from kdcube_ai_app.apps.chat.sdk.events.decorator import (
    EVENT_SOURCE_ATTR,
    EventSourceDeclaration,
    event_source,
    event_source_declaration,
    get_event_source_declaration,
)
from kdcube_ai_app.apps.chat.sdk.events.constants import (
    DEFAULT_REACT_AGENT_ID,
    normalize_agent_id,
    safe_event_lane_part,
)
from kdcube_ai_app.apps.chat.sdk.events.subsystem import (
    EventSourceSubsystem,
    ResolvedEventSource,
    resolve_event_source_specs,
)
from kdcube_ai_app.apps.chat.sdk.events.external import (
    EventTimelineIdentityCard,
    ExternalEventMaterializationCtx,
    ExternalEventMaterializationResult,
)

__all__ = [
    "EVENT_SOURCE_ATTR",
    "DEFAULT_REACT_AGENT_ID",
    "EventSourceDeclaration",
    "EventSourceSubsystem",
    "EventTimelineIdentityCard",
    "ExternalEventMaterializationCtx",
    "ExternalEventMaterializationResult",
    "ResolvedEventSource",
    "event_source",
    "event_source_declaration",
    "get_event_source_declaration",
    "normalize_agent_id",
    "resolve_event_source_specs",
    "safe_event_lane_part",
]
