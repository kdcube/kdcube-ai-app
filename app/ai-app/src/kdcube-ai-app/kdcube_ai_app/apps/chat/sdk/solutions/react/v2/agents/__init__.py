# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
_SHARED_DIR = _PKG_DIR.parent.parent / "agents"

__path__ = [str(_PKG_DIR), str(_SHARED_DIR)]
