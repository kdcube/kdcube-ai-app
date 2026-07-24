# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Async expansion of stored custom instruction refs into composer tokens.

The composer (``compose.py``) is sync and pure; the store is async. This pass
bridges them: it walks an item list, replaces every
``instr:custom:<id>[:<version>]`` token with the stored instruction's own item
list (recursively — stored instructions may reference other stored
instructions), and returns a flat token list the composer handles without any
store access.

Guarantees:
- **Nothing leaks.** A ref that cannot be resolved (unknown id/version,
  store error, malformed ref) is dropped with a warning — never passed through
  as literal prompt text.
- **Cycles terminate.** A stored instruction referencing itself (directly or
  through a chain) expands each (id, version) at most once per branch; a
  repeated ref inside its own expansion is dropped with a warning.
- **Depth is capped** (:data:`MAX_EXPANSION_DEPTH`) as a backstop.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.refs import (
    INSTR_CUSTOM_PREFIX,
    parse_custom_ref,
)

LOGGER = logging.getLogger(__name__)

MAX_EXPANSION_DEPTH = 8


def has_custom_instruction_refs(items: Optional[Iterable[str]]) -> bool:
    """True when any item is an ``instr:custom:`` token (parseable or not)."""
    if isinstance(items, str):
        items = [items]
    for item in items or []:
        if str(item or "").strip().lower().startswith(INSTR_CUSTOM_PREFIX):
            return True
    return False


async def expand_instruction_items(
    items: Optional[Iterable[str]],
    *,
    store: Any,
) -> list[str]:
    """Return ``items`` with every custom ref replaced by its stored item list.

    ``store`` is an :class:`AgenticInstructionsStore` (or anything providing
    ``async get(instruction_id, version=None) -> Optional[dict]`` where the
    dict carries ``version`` and ``items``).
    """
    if isinstance(items, str):
        items = [items]
    return await _expand(list(items or []), store=store, seen=frozenset(), depth=0)


async def _expand(
    items: list[Any],
    *,
    store: Any,
    seen: frozenset,
    depth: int,
) -> list[str]:
    out: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        if not text.lower().startswith(INSTR_CUSTOM_PREFIX):
            out.append(text)
            continue
        ref = parse_custom_ref(text)
        if ref is None:
            LOGGER.warning("[agentic_config] malformed custom instruction ref dropped: %s", text)
            continue
        if depth >= MAX_EXPANSION_DEPTH:
            LOGGER.warning(
                "[agentic_config] expansion depth cap reached; ref dropped: %s", text
            )
            continue
        try:
            record = await store.get(ref.instruction_id, ref.version)
        except Exception:
            LOGGER.warning(
                "[agentic_config] custom instruction fetch failed; ref dropped: %s",
                text,
                exc_info=True,
            )
            continue
        if not isinstance(record, dict) or not isinstance(record.get("items"), list):
            LOGGER.warning(
                "[agentic_config] custom instruction not found; ref dropped: %s", text
            )
            continue
        key = (ref.instruction_id, int(record.get("version") or 0))
        if key in seen:
            LOGGER.warning(
                "[agentic_config] cyclic custom instruction ref dropped: %s", text
            )
            continue
        nested = await _expand(
            [str(v or "") for v in record["items"]],
            store=store,
            seen=seen | {key},
            depth=depth + 1,
        )
        out.extend(nested)
    return out


__all__ = ["MAX_EXPANSION_DEPTH", "expand_instruction_items", "has_custom_instruction_refs"]
