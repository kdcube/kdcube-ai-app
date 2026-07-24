# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""The ``instr:`` ref grammar for instruction sets.

Two namespaces, usable wherever instruction items are listed (a descriptor's
``instruction_profiles[].blocks`` or ``instructions:`` list, or a stored
custom instruction's own item list):

- ``instr:profile:full | lite | extra-lite`` — a predefined set. Thin aliases
  onto the composer's existing tokens (``full``, ``lite:all_capabilities``,
  ``xlite:workspace_exec``); resolved synchronously, no store involved.
- ``instr:custom:<id>[:<version>]`` — a stored instruction (tenant/project
  scoped). ``<id>`` is a slug; ``<version>`` a positive integer; omitted
  version means the latest active one. Resolved by the async expand pass
  (``expand.py``) against ``AgenticInstructionsStore``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

INSTR_REF_PREFIX = "instr:"
INSTR_PROFILE_PREFIX = "instr:profile:"
INSTR_CUSTOM_PREFIX = "instr:custom:"

# Predefined set name -> composer token. One place; the widget and docs read it.
PROFILE_SET_ALIASES: dict[str, str] = {
    "full": "full",
    "lite": "lite:all_capabilities",
    "extra-lite": "xlite:workspace_exec",
}

_INSTRUCTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class CustomInstructionRef:
    """A parsed ``instr:custom:<id>[:<version>]`` ref."""

    instruction_id: str
    version: Optional[int] = None

    def token(self) -> str:
        return format_custom_ref(self.instruction_id, self.version)


def is_valid_instruction_id(value: str) -> bool:
    """Slug ids: lowercase alphanumerics and dashes, must not start with a dash."""
    return bool(_INSTRUCTION_ID_RE.match(str(value or "")))


def format_custom_ref(instruction_id: str, version: Optional[int] = None) -> str:
    base = f"{INSTR_CUSTOM_PREFIX}{instruction_id}"
    return f"{base}:{int(version)}" if version is not None else base


def resolve_profile_alias(text: str) -> Optional[str]:
    """Return the composer token for an ``instr:profile:<set>`` ref, else None.

    An ``instr:profile:`` ref naming an unknown set resolves to None — the
    caller treats it like any other unresolvable ref (dropped with a warning),
    never as literal prompt text.
    """
    raw = str(text or "").strip()
    if not raw.lower().startswith(INSTR_PROFILE_PREFIX):
        return None
    set_name = raw[len(INSTR_PROFILE_PREFIX):].strip().lower()
    return PROFILE_SET_ALIASES.get(set_name)


def parse_custom_ref(text: str) -> Optional[CustomInstructionRef]:
    """Parse ``instr:custom:<id>[:<version>]``; None when the text is not one.

    A malformed custom ref (bad slug, bad version) returns None as well — the
    expand pass logs and drops it so it can never leak into a prompt.
    """
    raw = str(text or "").strip()
    if not raw.lower().startswith(INSTR_CUSTOM_PREFIX):
        return None
    rest = raw[len(INSTR_CUSTOM_PREFIX):].strip()
    if not rest:
        return None
    instruction_id, _, version_part = rest.partition(":")
    instruction_id = instruction_id.strip().lower()
    if not is_valid_instruction_id(instruction_id):
        return None
    version_part = version_part.strip()
    if not version_part:
        return CustomInstructionRef(instruction_id=instruction_id)
    if not version_part.isdigit() or int(version_part) < 1:
        return None
    return CustomInstructionRef(instruction_id=instruction_id, version=int(version_part))


def find_custom_refs(items: Optional[Iterable[str]]) -> list[CustomInstructionRef]:
    """All parseable custom refs in an item list, in order, duplicates kept."""
    if isinstance(items, str):
        items = [items]
    found: list[CustomInstructionRef] = []
    for item in items or []:
        ref = parse_custom_ref(str(item or ""))
        if ref is not None:
            found.append(ref)
    return found


__all__ = [
    "CustomInstructionRef",
    "INSTR_CUSTOM_PREFIX",
    "INSTR_PROFILE_PREFIX",
    "INSTR_REF_PREFIX",
    "PROFILE_SET_ALIASES",
    "find_custom_refs",
    "format_custom_ref",
    "is_valid_instruction_id",
    "parse_custom_ref",
    "resolve_profile_alias",
]
