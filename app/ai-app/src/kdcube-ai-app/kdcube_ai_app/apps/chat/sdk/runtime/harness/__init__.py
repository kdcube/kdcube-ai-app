# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""Shared agent harness runtime.

This is the umbrella above framework adapters such as ReAct and LangGraph.
Its scopes stay separate:

* ``events`` resolves canonical event and object references;
* ``timeline`` owns block identity, organization, projection, and rendering;
* ``workspace`` owns distributed turn layout and file materialization.

Import from the owning scope. The umbrella deliberately does not flatten the
scope APIs.
"""

from kdcube_ai_app.apps.chat.sdk.runtime.harness import events, timeline, workspace

__all__ = ["events", "timeline", "workspace"]
