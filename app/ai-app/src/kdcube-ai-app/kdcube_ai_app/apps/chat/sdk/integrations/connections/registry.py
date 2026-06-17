"""ConnectionProvider registry — the per-provider declaration for OAuth connections.

A `ConnectionProvider` is PURE OAuth *mechanics*: the authorize/token endpoints,
the provider's default/required scopes, and how to identify the connected user
(`fetch_profile`). It carries NO credentials — no client_id, no client_secret,
no config/secret prefixes. Credentials live in *client apps* (admin data; see
`apps.py`), and there can be many client apps per provider.

Everything generic (token storage, state signing, callback route, settings ops)
lives in the sibling `store`/`oauth`/`settings` modules.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kdcube.integrations.connections")

# Fallback bundle id used when an entrypoint exposes none. Mirrors accounts.py.
DEFAULT_BUNDLE_ID = "task-and-memo-app@1-0"


def _entrypoint_bundle_id(entrypoint: Any, default: str = DEFAULT_BUNDLE_ID) -> str:
    for candidate in (
        getattr(getattr(getattr(entrypoint, "config", None), "ai_bundle_spec", None), "id", ""),
        getattr(getattr(entrypoint, "config", None), "bundle_id", ""),
        getattr(entrypoint, "bundle_id", ""),
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    return str(default or DEFAULT_BUNDLE_ID).strip() or DEFAULT_BUNDLE_ID


class ConnectionProvider(ABC):
    """Per-provider OAuth *mechanics* declaration (no credentials).

    Subclasses set the class attributes below; a provider with no method
    overrides gets the standard authorization-code flow for free. Credentials
    (client_id / client_secret / per-app scopes) come from a *client app* —
    see `apps.py` — not from the provider.
    """

    # ── identity / catalog ──────────────────────────────────────────────────
    provider: str = ""
    label: str = ""

    # ── OAuth endpoints ─────────────────────────────────────────────────────
    authorize_url: str = ""
    token_url: str = ""
    # The provider's default / required scopes. A client app's scopes are unioned
    # with these when building the authorize URL.
    scopes: List[str] = []

    # ── optional per-provider authorize tuning ──────────────────────────────

    def authorize_extra_params(self) -> Dict[str, Any]:
        """Extra query params merged into the authorize URL (default none).

        Lets a provider request provider-specific behaviour at consent time — e.g.
        Google's `access_type=offline` / `prompt=consent` to mint a refresh_token.
        Standard providers need none, so the default is empty.
        """
        return {}

    def authorize_scope_param(self) -> str:
        """Query-param name that carries the requested scopes in the authorize URL.

        Standard OAuth uses ``scope``. Slack user-token apps use ``user_scope`` so
        the install grants a USER token (acting AS the connecting user — e.g.
        `search:read` over their own messages) instead of a bot token.
        """
        return "scope"

    def extract_token(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a token-endpoint response into the stored token dict
        (`{access_token, scope?, refresh_token?, expires_in?}`).

        Default: standard OAuth2 — the response's top-level fields are the token.
        Providers like Slack override this to pull the USER token from
        ``authed_user`` (the initial exchange) and to surface logical errors
        (Slack returns ``ok: false`` with HTTP 200, not a 4xx).
        """
        return dict(raw or {})

    # ── per-provider profile identification ─────────────────────────────────

    @abstractmethod
    async def fetch_profile(self, *, access_token: str) -> Dict[str, Any]:
        """Identify the connected user.

        Returns normalized account fields:
            {
              "external_user_id": <the connected USER's id in the external system
                                   (Slack user, LinkedIn `sub`, Gmail address)>,
              "workspace":        <optional org/team id; a separate dimension>,
              "display_name":     <human label>,
              "email":            <optional>,
              "scope":            <list[str], optional>,
            }
        The account id is seeded from (workspace, external_user_id).
        """
        raise NotImplementedError


# ── module-level registry ──────────────────────────────────────────────────

_REGISTRY: Dict[str, ConnectionProvider] = {}


def register(provider: ConnectionProvider) -> ConnectionProvider:
    """Register a ConnectionProvider instance (or class) by its `provider` name."""
    inst = provider() if isinstance(provider, type) else provider
    name = str(getattr(inst, "provider", "") or "").strip()
    if not name:
        raise ValueError("ConnectionProvider.provider must be a non-empty string")
    _REGISTRY[name] = inst
    return inst


def connection_provider(name: str = ""):
    """Class decorator: register a ConnectionProvider subclass.

    @connection_provider("slack")
    class SlackConnection(ConnectionProvider): ...
    """
    def _decorator(cls):
        inst = cls()
        resolved = str(name or getattr(inst, "provider", "") or "").strip()
        if not resolved:
            raise ValueError("connection_provider requires a provider name")
        # keep the class attribute authoritative
        inst.provider = resolved
        _REGISTRY[resolved] = inst
        return cls
    return _decorator


def resolve(name: str) -> ConnectionProvider:
    key = str(name or "").strip()
    provider = _REGISTRY.get(key)
    if provider is None:
        raise KeyError(f"unknown connection provider: {key!r}")
    return provider


def catalog() -> List[ConnectionProvider]:
    """Registered providers, sorted by label/provider for stable UI ordering."""
    return sorted(
        _REGISTRY.values(),
        key=lambda p: str(getattr(p, "label", "") or getattr(p, "provider", "")),
    )


def get(name: str) -> Optional[ConnectionProvider]:
    return _REGISTRY.get(str(name or "").strip())
