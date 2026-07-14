# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import re
from typing import Any, Dict, Optional


DEFAULT_REACT_AGENT_ID = "default.react.agent"


def resolve_request_identity(comm: Any, *, runtime_ctx: Any = None) -> Dict[str, str]:
    """The turn's identity, resolved from ONE canonical source.

    The download-critical field is ``owner`` (the user a hosted file belongs to):
    the WRITE side (a tool hosting a file) and the READ side (the download resolver)
    must resolve the SAME user, or a file is stored under a key the download cannot
    reconstruct — and, worse for a per-user product, is not correctly bound to the
    user. Every identity surface across the codebase reads ``comm.service`` (the
    request's service context) first, then falls back to the communicator's own
    attributes (see ``react/tools/common.py``, ``tools/bundle_tool_context.py``); this
    centralizes that precedence so no caller re-derives it (and gets it subtly wrong).

    Returns ``{tenant, project, owner, user_type, conversation_id, request_id}`` —
    empty strings for anything unresolved.
    """
    service = getattr(comm, "service", None) or {}
    if not isinstance(service, dict):
        service = {}

    def _pick(key: str, *fallbacks: Any) -> str:
        val = str(service.get(key) or "").strip()
        for fb in fallbacks:
            if val:
                break
            val = str(fb or "").strip()
        return val

    return {
        "tenant": _pick("tenant", getattr(comm, "tenant", None)),
        "project": _pick("project", getattr(comm, "project", None)),
        "owner": _pick("user", getattr(comm, "user_id", None)),
        "user_type": _pick("user_type", getattr(comm, "user_type", None)),
        "conversation_id": _pick("conversation_id", getattr(runtime_ctx, "conversation_id", None)),
        "request_id": _pick("request_id"),
    }


def normalize_agent_id(value: object, *, default: str = DEFAULT_REACT_AGENT_ID) -> str:
    """Return the stable target-agent id used by event lanes."""

    text = str(value or "").strip()
    if not text:
        text = str(default or "").strip()
    return text or DEFAULT_REACT_AGENT_ID


def index_agent_id(value: object) -> Optional[str]:
    """Storage value for conv_messages.agent_id: the agent id as-is, or None when absent."""

    return str(value or "").strip() or None


def safe_event_lane_part(value: object, *, default: str = "_") -> str:
    """Normalize one identity component for Redis event-lane keys."""

    text = str(value or "").strip() or str(default or "_")
    text = re.sub(r"[^A-Za-z0-9_.@-]+", "_", text)
    return text or "_"


def safe_event_object_path(value: object, *, default: str = "event") -> str:
    """Normalize an event object path used below the `ev:...events/` root."""

    text = str(value or "").strip().strip("/")
    if not text:
        text = str(default or "event").strip().strip("/") or "event"
    parts = []
    for part in text.split("/"):
        clean = re.sub(r"[^A-Za-z0-9_.@-]+", "_", part.strip())
        clean = clean.strip("._")
        if clean:
            parts.append(clean)
    return "/".join(parts) or "event"


def build_event_logical_path(
    *,
    turn_id: str,
    event_path: object,
    conversation_id: object | None = None,
) -> str:
    """Build the logical `ev:` reference for an event object on a turn timeline."""

    turn = str(turn_id or "").strip()
    if not turn:
        raise ValueError("turn_id is required to build an event logical path")
    path = safe_event_object_path(event_path)
    conv = str(conversation_id or "").strip()
    if conv:
        return f"ev:conv_{conv}.{turn}.events/{path}"
    return f"ev:{turn}.events/{path}"
