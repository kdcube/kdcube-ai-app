# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Event-source declarations and discovery for chat SDK runtimes."""

from kdcube_ai_app.apps.chat.sdk.events.decorator import (
    ARTIFACT_NAMESPACE_REHOSTER_ATTR,
    EVENT_SOURCE_ATTR,
    ArtifactNamespaceRehosterDeclaration,
    EventSourceDeclaration,
    artifact_namespace_rehoster,
    artifact_namespace_rehoster_declaration,
    event_source,
    event_source_declaration,
    get_artifact_namespace_rehoster_declaration,
    get_event_source_declaration,
)
from kdcube_ai_app.apps.chat.sdk.events.constants import (
    DEFAULT_REACT_AGENT_ID,
    normalize_agent_id,
    safe_event_lane_part,
)
from kdcube_ai_app.apps.chat.sdk.events.subsystem import (
    EventSourceSubsystem,
    ResolvedArtifactNamespaceRehoster,
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
    "ARTIFACT_NAMESPACE_REHOSTER_ATTR",
    "ArtifactNamespaceRehosterDeclaration",
    "DEFAULT_REACT_AGENT_ID",
    "EventSourceDeclaration",
    "EventSourceSubsystem",
    "EventTimelineIdentityCard",
    "ExternalEventMaterializationCtx",
    "ExternalEventMaterializationResult",
    "ResolvedArtifactNamespaceRehoster",
    "ResolvedEventSource",
    "artifact_namespace_rehoster",
    "artifact_namespace_rehoster_declaration",
    "event_source",
    "event_source_declaration",
    "get_artifact_namespace_rehoster_declaration",
    "get_event_source_declaration",
    "normalize_agent_id",
    "resolve_event_source_specs",
    "safe_event_lane_part",
]
