# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import re
from typing import Optional


DEFAULT_REACT_AGENT_ID = "default.react.agent"


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
