# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

from typing import Any, Dict, Optional


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _event_payload(event: Any) -> Dict[str, Any]:
    raw = getattr(event, "payload", None)
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def compute_reactive_iteration_credit_cap(*, runtime_ctx: Any, base_max_iterations: int) -> int:
    enabled = bool(getattr(runtime_ctx, "reactive_event_iteration_credit_enabled", True))
    if not enabled:
        return 0
    raw_cap = getattr(runtime_ctx, "reactive_event_iteration_credit_cap", None)
    if raw_cap is None:
        return max(0, int(base_max_iterations or 0))
    return max(0, _as_int(raw_cap, base_max_iterations))


def resolve_reactive_iteration_credit(
    *,
    event_type: str,
    event: Any,
    runtime_ctx: Any,
) -> int:
    enabled = bool(getattr(runtime_ctx, "reactive_event_iteration_credit_enabled", True))
    if not enabled:
        return 0
    type_norm = str(event_type or getattr(event, "kind", "") or "").strip().lower()
    if type_norm == "steer":
        return 0

    payload = _event_payload(event)
    policy = payload.get("timeline_event_policy") if isinstance(payload.get("timeline_event_policy"), dict) else {}

    explicit_reactive = policy.get("continue_react_when_active")
    if explicit_reactive is None:
        explicit_reactive = payload.get("continue_react_when_active")
    if explicit_reactive is None:
        explicit_reactive = payload.get("reactive")

    is_reactive = type_norm == "followup" or bool(explicit_reactive)
    if not is_reactive:
        return 0

    per_event = max(1, _as_int(getattr(runtime_ctx, "reactive_event_iteration_credit_per_event", 1), 1))
    override = policy.get("iteration_credit")
    if override is None:
        override = payload.get("iteration_credit")
    if override is not None:
        per_event = max(1, _as_int(override, per_event))
    return per_event


def sync_reactive_iteration_budget(*, state: Dict[str, Any], granted_credit: int) -> int:
    base = max(
        0,
        _as_int(
            state.get("base_max_iterations"),
            _as_int(state.get("max_iterations"), 0),
        ),
    )
    cap = max(0, _as_int(state.get("reactive_iteration_credit_cap"), 0))
    effective_credit = max(0, _as_int(granted_credit, 0))
    if cap:
        effective_credit = min(effective_credit, cap)
    else:
        effective_credit = 0
    state["base_max_iterations"] = base
    state["reactive_iteration_credit_cap"] = cap
    state["reactive_iteration_credit"] = effective_credit
    state["max_iterations"] = base + effective_credit
    return int(state["max_iterations"] or 0)
