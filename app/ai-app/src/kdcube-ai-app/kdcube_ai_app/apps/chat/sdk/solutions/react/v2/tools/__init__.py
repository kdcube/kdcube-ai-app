# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from importlib import import_module as _import_module
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
_SHARED_DIR = _PKG_DIR.parent.parent / "tools"
__path__ = [str(_PKG_DIR), str(_SHARED_DIR)]

_shared = _import_module("kdcube_ai_app.apps.chat.sdk.solutions.react.tools")
__all__ = list(getattr(_shared, "__all__", []))


def __getattr__(name: str):
    return getattr(_shared, name)


def __dir__():
    return sorted(set(list(globals().keys()) + list(__all__)))
