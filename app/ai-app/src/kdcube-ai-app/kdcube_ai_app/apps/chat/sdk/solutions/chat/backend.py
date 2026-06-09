"""Reusable chat solution mount helpers.

Bundles can mount the shared chat widget with ``chat_widget_ui_config()`` and
then provide their own event-source ids through Vite environment variables when
they need names different from the task-tracker-compatible defaults.
"""

from __future__ import annotations

from typing import Any


CHAT_WIDGET_SDK_SOURCE = "sdk://solutions/chat/ui/widget"
DEFAULT_CHAT_WIDGET_BUILD_COMMAND = (
    "npm install --no-package-lock && "
    "OUTDIR=<VI_BUILD_DEST_ABSOLUTE_PATH> npm run build"
)


def chat_widget_ui_config(
    *,
    enabled: bool = True,
    src_folder: str = CHAT_WIDGET_SDK_SOURCE,
    build_command: str = DEFAULT_CHAT_WIDGET_BUILD_COMMAND,
    **extra: Any,
) -> dict[str, Any]:
    """Return a bundle ``config.ui.widgets.<alias>`` entry for the chat widget."""

    return {
        "enabled": enabled,
        "src_folder": src_folder,
        "build_command": build_command,
        **extra,
    }


__all__ = [
    "CHAT_WIDGET_SDK_SOURCE",
    "DEFAULT_CHAT_WIDGET_BUILD_COMMAND",
    "chat_widget_ui_config",
]
