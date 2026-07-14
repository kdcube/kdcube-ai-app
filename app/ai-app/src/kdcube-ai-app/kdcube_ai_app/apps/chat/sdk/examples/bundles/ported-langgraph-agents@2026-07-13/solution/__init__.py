# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""Vendored, UNCHANGED standalone agents this app hosts, one subpackage each.

Both packages are the "before" instances of the KDCube port recipe, copied here
without edits to their graph logic:

  - ``lg_solution``  — the hand-written research graph (KB retrieval + per-user
                       pgvector memory + a nested subagent; a dedicated answer node).
  - ``lg_prebuilt``  — the standard ``langgraph.prebuilt.create_react_agent``
                       (a looping agent node + a tools node; plain + MCP tools).

The multi-agent host (``entrypoint.py``) dispatches on ``agent_id`` to the right
package; neither package imports KDCube.
"""

__all__ = ["lg_solution", "lg_prebuilt"]
