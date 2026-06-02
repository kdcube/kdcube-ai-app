# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import re


DEFAULT_REACT_AGENT_ID = "default.react.agent"


def normalize_agent_id(value: object, *, default: str = DEFAULT_REACT_AGENT_ID) -> str:
    """Return the stable target-agent id used by event lanes."""

    text = str(value or "").strip()
    if not text:
        text = str(default or "").strip()
    return text or DEFAULT_REACT_AGENT_ID


def safe_event_lane_part(value: object, *, default: str = "_") -> str:
    """Normalize one identity component for Redis event-lane keys."""

    text = str(value or "").strip() or str(default or "_")
    text = re.sub(r"[^A-Za-z0-9_.@-]+", "_", text)
    return text or "_"
