from __future__ import annotations

from typing import Any

DEFAULT_CANVAS_EVENT_SOURCE_SPECS: list[dict[str, Any]] = [
    {
        "module": "kdcube_ai_app.apps.chat.sdk.solutions.canvas.events.resolver",
        "alias": "canvas",
    },
]


def default_canvas_event_source_specs() -> list[dict[str, Any]]:
    return [dict(item) for item in DEFAULT_CANVAS_EVENT_SOURCE_SPECS]


__all__ = [
    "DEFAULT_CANVAS_EVENT_SOURCE_SPECS",
    "default_canvas_event_source_specs",
]
