# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

from importlib import import_module as _import_module

_shared = _import_module("kdcube_ai_app.apps.chat.sdk.solutions.react.timeline")
globals().update({k: v for k, v in _shared.__dict__.items() if not (k.startswith("__") and k.endswith("__"))})
__all__ = getattr(_shared, "__all__", [k for k in globals().keys() if not k.startswith("_")])
