# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Instruction sets as managed artifacts: vocabulary, refs, store, expansion.

- ``compose.py`` — the agent-neutral composer (one token list → one body).
- ``refs.py`` — the ``instr:profile:<set>`` / ``instr:custom:<id>[:<version>]``
  ref grammar.
- ``store.py`` — the versioned, provenance-carrying project-schema store.
- ``expand.py`` — the async pass that resolves stored custom refs into
  composer tokens BEFORE composition; the composer itself stays sync/pure.
"""

from __future__ import annotations

from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.catalog import (
    builtin_block_catalog,
)
from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.compose import (
    compose_instruction_body,
)
from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.expand import (
    expand_instruction_items,
    has_custom_instruction_refs,
)
from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.refs import (
    CustomInstructionRef,
    format_custom_ref,
    parse_custom_ref,
    resolve_profile_alias,
)
from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.store import (
    AgenticInstructionsStore,
)

__all__ = [
    "AgenticInstructionsStore",
    "builtin_block_catalog",
    "CustomInstructionRef",
    "compose_instruction_body",
    "expand_instruction_items",
    "format_custom_ref",
    "has_custom_instruction_refs",
    "parse_custom_ref",
    "resolve_profile_alias",
]
