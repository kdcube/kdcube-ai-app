# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Compatibility shim — the composer lives in ``agentic_config.instructions``.

The agent-neutral instruction seam grew into the ``agentic_config`` subsystem
(vocabulary + ``instr:`` refs + versioned store + async expansion). Import
from ``kdcube_ai_app.apps.chat.sdk.solutions.agentic_config`` going forward;
this module keeps the original import path working.
"""

from __future__ import annotations

from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.compose import (
    compose_instruction_body,
)

__all__ = ["compose_instruction_body"]
