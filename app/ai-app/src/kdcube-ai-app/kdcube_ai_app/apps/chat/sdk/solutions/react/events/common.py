# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import os
from typing import Any

_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}


def event_source_pipeline_enabled(owner: Any = None) -> bool:
    """Return whether ReAct should use the alternate event-source pipeline.

    The default is intentionally off. Runtime code may opt in through
    `RuntimeCtx.event_source_pipeline_enabled`, a matching attribute on a
    ReAct runtime object, or `KDCUBE_REACT_EVENT_SOURCE_PIPELINE=1` for local
    experiments.
    """

    def _bool_attr(obj: Any) -> bool | None:
        if obj is None:
            return None
        value = getattr(obj, "event_source_pipeline_enabled", None)
        if value is not None:
            return bool(value)
        runtime_ctx = getattr(obj, "runtime_ctx", None)
        if runtime_ctx is not None:
            value = getattr(runtime_ctx, "event_source_pipeline_enabled", None)
            if value is not None:
                return bool(value)
        ctx_browser = getattr(obj, "ctx_browser", None)
        if ctx_browser is not None:
            runtime_ctx = getattr(ctx_browser, "runtime_ctx", None)
            value = getattr(runtime_ctx, "event_source_pipeline_enabled", None)
            if value is not None:
                return bool(value)
        return None

    explicit = _bool_attr(owner)
    if explicit is not None:
        return bool(explicit)
    raw = (
        os.getenv("AI_REACT_EVENT_SOURCE_PIPELINE_ENABLED")
        or os.getenv("KDCUBE_REACT_EVENT_SOURCE_PIPELINE")
        or ""
    )
    return str(raw).strip().lower() in _TRUE_VALUES
