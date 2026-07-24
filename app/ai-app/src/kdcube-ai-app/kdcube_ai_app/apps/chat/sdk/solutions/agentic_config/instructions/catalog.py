# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""The block catalog — every composition unit the constructor can offer.

Built-in blocks come from the two in-tree registries (moderate
``REACT_LITE_*``, extra-lite ``REACT_XLITE_*``); each entry carries a derived
description (the block's own header line + first content line — so blocks are
DISTINGUISHABLE when browsing) and tags: its tier plus, for moderate blocks,
every profile that includes it. Stored custom units add their authored
description/tags on top (served by the store, not here).

The signal table in ``docs/sdk/agents/react/system-instruction-README.md``
remains the authoritative purpose map; descriptions here are derived hints
sized for pickers.
"""

from __future__ import annotations

import re
from typing import Any

from kdcube_ai_app.apps.chat.sdk.skills.instructions.shared_instructions_lite import (
    REACT_LITE_PROFILE_BLOCKS,
    list_lite_instruction_blocks,
)
from kdcube_ai_app.apps.chat.sdk.skills.instructions.instructions_extra_lite import (
    list_extra_lite_instruction_blocks,
)

_DESCRIPTION_LIMIT = 160


def _derive_description(text: str) -> str:
    """Header tag + first content sentence, picker-sized."""
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    head = lines[0]
    body = ""
    if re.fullmatch(r"\[[^\]]+\]", head) and len(lines) > 1:
        body = lines[1]
    elif re.match(r"^\[[^\]]+\]", head):
        body = head[head.index("]") + 1 :].strip()
        head = head[: head.index("]") + 1]
    out = f"{head} {body}".strip() if body else head
    if len(out) > _DESCRIPTION_LIMIT:
        out = out[: _DESCRIPTION_LIMIT - 1].rstrip() + "…"
    return out


def builtin_block_catalog() -> list[dict[str, Any]]:
    """Every built-in block as ``{name, tier, description, tags}``.

    Tags: the tier (``moderate`` | ``extra-lite``) and, for moderate blocks,
    each profile whose expansion includes the block — so a picker can filter
    "everything the web profile teaches" or "extra-lite only".
    """
    profile_tags: dict[str, list[str]] = {}
    for profile, blocks in (REACT_LITE_PROFILE_BLOCKS or {}).items():
        for name in blocks or ():
            profile_tags.setdefault(str(name), []).append(str(profile))

    catalog: list[dict[str, Any]] = []
    for name, text in sorted(list_lite_instruction_blocks().items()):
        catalog.append(
            {
                "name": name,
                "tier": "moderate",
                "description": _derive_description(text),
                "tags": ["moderate", *sorted(profile_tags.get(name, []))],
            }
        )
    for name, text in sorted(list_extra_lite_instruction_blocks().items()):
        catalog.append(
            {
                "name": name,
                "tier": "extra-lite",
                "description": _derive_description(text),
                "tags": ["extra-lite"],
            }
        )
    return catalog


__all__ = ["builtin_block_catalog"]
