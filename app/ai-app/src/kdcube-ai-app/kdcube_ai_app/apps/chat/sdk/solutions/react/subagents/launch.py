# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""The launch contract between ``react.delegate`` and the host spawner.

The react runtime never constructs a child agent itself: the host workflow
(the layer that builds react agents) injects a spawner onto
``runtime_ctx.subagent_spawner``. The tool handler builds a
``SubagentLaunchRequest`` and awaits ``spawner.spawn(request)``, which
returns a ``SubagentLaunchTicket`` immediately — the child runs on in the
background.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.charter import SubagentCharter
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.events import ParentLaneAddress


@dataclass
class SubagentLaunchRequest:
    charter: SubagentCharter
    parent: ParentLaneAddress
    # The fork projection: seed blocks for the child conversation (already
    # conversation-qualified where needed).
    fork_blocks: List[Dict[str, Any]] = field(default_factory=list)
    # Parent run configuration the child inherits.
    allowed_plugins: Optional[List[str]] = None
    allowed_tool_names_by_alias: Optional[Dict[str, Any]] = None
    # Depth of the REQUESTING agent; the child runs at depth + 1.
    parent_depth: int = 0
    tool_call_id: str = ""


@dataclass
class SubagentLaunchTicket:
    child_conversation_id: str
    child_turn_id: str
    status: str = "started"
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "child_conversation_id": self.child_conversation_id,
            "child_conversation_ref": f"conv_{self.child_conversation_id}",
            "child_turn_id": self.child_turn_id,
            "status": self.status,
            **({"error": self.error} if self.error else {}),
        }
