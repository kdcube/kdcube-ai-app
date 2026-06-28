# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
#
# ── entrypoint.py ──
# user-memories — a memory-only app.
#
# Goal:
#   Expose the user's memories ONCE, as a standalone surface (the SDK memories
#   widget + the `mem` named service), so other apps/scenes embed it by iframe
#   instead of each republishing the memory module. This is the cleaner paradigm
#   than the current "embedded module" approach (e.g. in `versatile`).
#
# How:
#   The entrypoint derives BaseEntrypointWithEconomicsAndMemory, which already
#   wires the memory subsystem (widget operations + the `mem` named-service
#   provider) and the economics guard. This app only ENABLES the memory widget
#   and points the build at the SDK widget source — it ships no UI of its own.
#
# Served surfaces (provided by the mixin once memory is enabled):
#   - widget  `memories`  -> /api/integrations/bundles/{tenant}/{project}/user-memories@2026-06-26/widgets/memories
#   - named service `mem` -> registered for cross-app consumption (discovery via Redis)

from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import StateGraph, START, END

from kdcube_ai_app.apps.chat.sdk.protocol import ExternalEventPayload, external_events_text
from kdcube_ai_app.infra.service_hub.inventory import Config, BundleState
from kdcube_ai_app.infra.plugin.bundle_loader import bundle_entrypoint, bundle_id
from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint_with_memory import (
    BaseEntrypointWithEconomicsAndMemory,
)

BUNDLE_ID = "user-memories@2026-06-26"
WORKFLOW_NAME = "user_memories"

# The memories widget is built from the SDK source (shared, single copy). This
# app does NOT keep its own ui/ folder — the platform materializes the widget at
# build time from this src_folder.
MEMORY_WIDGET_SRC = "sdk://context/memory/ui/widget/memories"
WIDGET_BUILD_COMMAND = (
    "npm install --no-package-lock && OUTDIR=<VI_BUILD_DEST_ABSOLUTE_PATH> npm run build"
)


@bundle_entrypoint(
    name=WORKFLOW_NAME,
    version="1.0.0",
    priority=100,
    allowed_roles_config="visibility.bundle.allowed_roles",
)
@bundle_id(id=BUNDLE_ID)
class UserMemoriesEntrypoint(BaseEntrypointWithEconomicsAndMemory):
    """Memory-only app: serves the SDK user-memories widget and the `mem` named
    service. No chat product surface, no embedded memory copy — other apps embed
    this widget by iframe and consume `mem` as a named service."""

    def __init__(
        self,
        config: Config,
        pg_pool: Any = None,
        redis: Any = None,
        comm_context: ExternalEventPayload = None,
    ):
        super().__init__(
            config=config,
            pg_pool=pg_pool,
            redis=redis,
            comm_context=comm_context,
        )
        # The base entrypoint expects a workflow graph; this app has no chat
        # product, so the graph is a no-op that points callers at the widget.
        self.graph = self._build_graph()

    def configuration_defaults(self) -> Dict[str, Any]:
        defaults = {
            "visibility": {
                "bundle": {"allowed_roles": []},
                "widget": {
                    "memories": {"user_types": [], "roles": []},
                },
            },
            # Enable the memory subsystem. The mixin's memory_configuration_defaults()
            # fill in the rest (reconciliation, snapshots, schema). Announce/tools
            # stay off — this app has no chat agent to inject memories into; the
            # WIDGET (and the `mem` named service) are the product.
            "memory": {
                "enabled": True,
                "announce": {"enabled": False},
                "tools": {"enabled": False},
                "widget": {
                    "enabled": True,
                    "allow_write": True,
                    # This is the dedicated memory surface, so default to the
                    # user's whole memory set across apps, not one app's slice.
                    "default_scope_filter": "all_user_memories",
                    "allow_all_user_memories": True,
                    "limit": 30,
                },
            },
            "ui": {
                "widgets": {
                    "memories": {
                        "enabled": True,
                        "src_folder": MEMORY_WIDGET_SRC,
                        "build_command": WIDGET_BUILD_COMMAND,
                    },
                },
            },
        }
        return self._deep_merge_props(super().configuration_defaults(), defaults)

    def _build_graph(self) -> StateGraph:
        g = StateGraph(BundleState)

        async def note(state: BundleState) -> BundleState:
            # No chat product here. If a message ever reaches this app, point the
            # caller at the widget rather than failing.
            _ = external_events_text(state.get("external_events") or [])
            state["final_answer"] = (
                "This app serves your memories. Open the Memories widget to search, "
                "add, and manage them."
            )
            return state

        g.add_node("note", note)
        g.add_edge(START, "note")
        g.add_edge("note", END)
        return g.compile()

    async def execute_core(
        self,
        *,
        state: Dict[str, Any],
        thread_id: str,
        params: Dict[str, Any],
    ):
        return await self.graph.ainvoke(state)
