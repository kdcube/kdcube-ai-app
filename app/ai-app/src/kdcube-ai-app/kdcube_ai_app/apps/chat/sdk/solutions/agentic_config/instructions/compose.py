# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Agent-neutral composition of an instruction body from config tokens.

One vocabulary, shared by any agent that composes its instruction body from a
configured list (a profile's ``blocks``, or ``instruction_blocks``). Each item
is resolved independently and all are joined with a blank line **in the order
listed**:

- ``full`` (optionally ``full:<anything>``) → the agent's complete default body,
  supplied by the caller through ``full_body_provider``. The full set is
  monolithic (not capability-scoped), so any suffix is ignored. With no provider
  a ``full`` token contributes nothing.
- ``lite:<profile>`` → a whole moderate profile body (``core``, ``workspace``,
  ``workspace_exec``, ``document``, ``web``, ``all_capabilities``).
- ``xlite:<profile>`` → a whole extra-lite profile body (same profile names).
- ``REACT_LITE_*`` / ``REACT_XLITE_*`` → a single named block.
- ``instr:profile:full|lite|extra-lite`` → a predefined set; a thin alias onto
  the tokens above (see ``refs.PROFILE_SET_ALIASES``).
- ``instr:custom:<id>[:<version>]`` → a stored instruction. Custom refs are
  resolved by the ASYNC expand pass (``expand.expand_instruction_items``)
  before composition; the composer is sync/pure. An unexpanded custom ref is
  dropped with a warning — it never leaks into a prompt as literal text.
- anything else → literal instruction text, used verbatim.

This module owns only the vocabulary. The agent's full/default body is injected
(``full_body_provider``) so nothing here is agent-specific; the ReAct harness,
or any other agent, wraps this with its own default-body builder. The runtime
protocol and tool/skill catalogs are added by the agent around this body, not
here.

Stored instruction sets live in ``store.AgenticInstructionsStore``
(tenant/project scoped, versioned, provenance-carrying); the ref grammar is
``refs.py``. Keep any new resolution behind this composer so callers never
change.
"""

from __future__ import annotations

import logging
from typing import Callable, Iterable, Optional

from kdcube_ai_app.apps.chat.sdk.skills.instructions.shared_instructions_lite import (
    resolve_lite_item,
)
from kdcube_ai_app.apps.chat.sdk.skills.instructions.instructions_extra_lite import (
    resolve_extra_lite_item,
)
from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.refs import (
    INSTR_CUSTOM_PREFIX,
    INSTR_PROFILE_PREFIX,
    resolve_profile_alias,
)

LOGGER = logging.getLogger(__name__)


def compose_instruction_body(
    items: Optional[Iterable[str]],
    *,
    workspace_implementation: str = "custom",
    full_body_provider: Optional[Callable[[], str]] = None,
    exclude_blocks: Optional[Iterable[str]] = None,
) -> str:
    """Compose a config token list into one instruction body (order-preserving).

    ``workspace_implementation`` is passed to profile expansion so
    ``lite:``/``xlite:`` honor git mode. ``full_body_provider`` supplies the
    agent's complete default body for a ``full`` token. ``exclude_blocks``
    names single blocks to omit — both as top-level items and inside expanded
    ``lite:``/``xlite:`` profiles.
    """
    if isinstance(items, str):
        items = [items]
    excluded = {str(name or "").strip() for name in (exclude_blocks or [])}
    resolved: list[str] = []
    for item in items or []:
        text = str(item or "").strip()
        if not text:
            continue
        if text in excluded:
            continue
        low = text.lower()
        if low.startswith(INSTR_PROFILE_PREFIX):
            alias = resolve_profile_alias(text)
            if alias is None:
                LOGGER.warning(
                    "[agentic_config] unknown predefined instruction set dropped: %s", text
                )
                continue
            text = alias
            low = text.lower()
        if low.startswith(INSTR_CUSTOM_PREFIX):
            # Custom refs resolve from the store BEFORE composition (the async
            # expand pass). An unexpanded ref never leaks into a prompt.
            LOGGER.warning(
                "[agentic_config] unexpanded custom instruction ref dropped: %s", text
            )
            continue
        if low == "full" or low.startswith("full:"):
            body = (full_body_provider() if full_body_provider is not None else "").strip()
            if body:
                resolved.append(body)
            continue
        xlite = resolve_extra_lite_item(
            text,
            workspace_implementation=workspace_implementation,
            exclude_blocks=excluded,
        )
        if xlite is not None:
            resolved.append(xlite)
            continue
        lite = resolve_lite_item(text, exclude_blocks=excluded)
        if lite is not None:
            resolved.append(lite)
            continue
        resolved.append(text)  # literal instruction fragment
    return "\n\n".join(part for part in (p.strip() for p in resolved) if part).strip()


__all__ = ["compose_instruction_body"]
