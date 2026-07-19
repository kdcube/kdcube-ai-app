# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Request-scoped per-agent account binding for connected-account resolution.

The broker (`delegated_to_kdcube.broker.ensure_claim`) decides which connected
account satisfies a provider claim. The calling AGENT may be bound to specific
account(s) per provider (`account_scope: {provider_id: [account_ids or "*"]}` on
its grant card). That binding must reach the broker, but the shared resolver
(`integrations.connected_accounts.resolve_connected_account_claim`) runs
downstream of the door through a generic transport with no HTTP request.

Whoever HAS the agent's credential sets the binding into this contextvar at the
boundary — the door bridge from `request.state.delegated_credential`; a native
agent gate from the same view — and the resolver reads back the allowed set for
the provider it is resolving. Unset / non-agent turns resolve to None (no
restriction), so the default behavior is unchanged.
"""

from __future__ import annotations

import contextvars
from typing import Any, Mapping

_ACCOUNT_SCOPE: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "kdcube_agent_account_scope", default={}
)


def set_agent_account_scope(scope: Mapping[str, Any] | None) -> None:
    """Bind the current agent's account scope ({provider_id: [account_ids]})."""
    _ACCOUNT_SCOPE.set({
        str(provider).strip(): [str(a).strip() for a in (accounts or []) if str(a or "").strip()]
        for provider, accounts in dict(scope or {}).items()
        if str(provider or "").strip()
    })


def clear_agent_account_scope() -> None:
    _ACCOUNT_SCOPE.set({})


def allowed_account_ids_for(provider_id: str) -> set[str] | None:
    """The account ids the current agent may use for ``provider_id`` — a set to
    restrict candidates to, or None for no restriction ("*"/absent/any)."""
    entry = _ACCOUNT_SCOPE.get().get(str(provider_id or "").strip())
    if not entry:
        return None
    allowed = {str(a).strip() for a in entry if str(a or "").strip()}
    if not allowed or "*" in allowed:
        return None
    return allowed


__all__ = [
    "set_agent_account_scope",
    "clear_agent_account_scope",
    "allowed_account_ids_for",
]
