# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
#
# ── skills_descriptor.py ──
# Declares which skills (prompt templates) are available to the react.code solver.

from __future__ import annotations

import pathlib
from typing import Optional, Dict, Any

BUNDLE_ROOT = pathlib.Path(__file__).resolve().parent

CUSTOM_SKILLS_ROOT: Optional[pathlib.Path] = BUNDLE_ROOT / "skills"

AGENTS_CONFIG: Dict[str, Dict[str, Any]] = {
    "solver.react.decision.v2": {}
}
