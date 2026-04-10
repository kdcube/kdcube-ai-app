# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
#
# ── tools/react_tools.py ──
# Bundle-local tool: react.search_knowledge
#
# Provides the LLM agent with the ability to search the knowledge space
# index (index.json) for relevant docs by keyword matching. Registered
# as a Semantic Kernel plugin with alias "react" in tools_descriptor.py,
# so the tool ID becomes "react.search_knowledge".
#
# The bundle package is loaded under a real dynamic package root, so normal
# same-bundle relative imports work here. Proc-side tool binding seeds
# KNOWLEDGE_ROOT from bundle storage when needed; isolated exec falls back to
# BUNDLE_STORAGE_DIR.

from __future__ import annotations

from typing import Annotated, Optional, Any

import semantic_kernel as sk

try:
    from semantic_kernel.functions import kernel_function
except Exception:
    from semantic_kernel.utils.function_decorator import kernel_function

from kdcube_ai_app.infra.plugin.bundle_storage import storage_for_spec
from ..knowledge import resolver as knowledge_resolver

_TOOL_SUBSYSTEM: Any = None


def _seed_knowledge_root_from_tool_context() -> None:
    global _TOOL_SUBSYSTEM
    if _TOOL_SUBSYSTEM is None:
        return
    if getattr(knowledge_resolver, "KNOWLEDGE_ROOT", None):
        return
    spec = getattr(_TOOL_SUBSYSTEM, "bundle_spec", None)
    comm = getattr(_TOOL_SUBSYSTEM, "comm", None)
    tenant = getattr(comm, "tenant", None)
    project = getattr(comm, "project", None)
    root = storage_for_spec(
        spec=spec,
        tenant=tenant,
        project=project,
        ensure=True,
    )
    if root is not None:
        knowledge_resolver.KNOWLEDGE_ROOT = root


def bind_integrations(integrations):
    global _TOOL_SUBSYSTEM
    _TOOL_SUBSYSTEM = (integrations or {}).get("tool_subsystem")
    _seed_knowledge_root_from_tool_context()


class KDCubeCopilotTools:
    """SK plugin exposing knowledge-space search to the ReAct agent."""
    @kernel_function(
        name="search_knowledge",
        description=(
            "Search the local knowledge space exposed by this bundle. "
            "Use this for product/architecture questions before external search."
        ),
    )
    async def search_knowledge(
        self,
        query: Annotated[str, "Search query for docs/knowledge index."],
        root: Annotated[Optional[str], "Optional subtree selector under ks:, for example ks:docs or ks:deployment (default: ks:docs)."] = "ks:docs",
        keywords: Annotated[Optional[list[str]], "Optional keywords/tags to bias ranking."] = None,
        top_k: Annotated[int, "Max hits to return (default 20)."] = 20,
    ) -> Annotated[list[dict] | None, "List of hits with ks: paths + titles."]:
        if not query or not str(query).strip():
            return []
        root_sel = (root or "ks:docs").strip()
        try:
            _seed_knowledge_root_from_tool_context()
            result = knowledge_resolver.search_knowledge(
                query=str(query).strip(),
                root=root_sel,
                max_hits=int(top_k or 20),
                keywords=keywords,
            )
            if hasattr(result, "__await__"):
                result = await result
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return list(result.get("hits") or [])
            return []
        except Exception:
            return []


# Module-level exports for SK + tool subsystem.
# The tool loader expects a `kernel` with registered plugins at module scope.
kernel = sk.Kernel()
tools = KDCubeCopilotTools()
kernel.add_plugin(tools, "kdcube_copilot_tools")
