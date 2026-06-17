"""Connections framework — generic OAuth integrations (Layer 1).

A registry-driven generalization of the per-integration accounts/settings
pattern: a new provider is a `ConnectionProvider` declaration, not a copy.
See docs/sdk/integrations/connections-README.md for the contract.
"""

from __future__ import annotations

from .registry import (
    ConnectionProvider,
    catalog,
    connection_provider,
    get,
    register,
    resolve,
)
from .store import ConnectionStore
from .apps import (
    ClientApp,
    AmbiguousClientApp,
    list_client_apps,
    resolve_client_app,
    client_app_secret,
    oauth_state_secret,
)
from .oauth import (
    ProviderHttpError,
    build_authorize_url,
    callback_url,
    exchange_code,
    refresh_access_token,
)
from .settings import (
    configure_connections,
    status,
    start_oauth,
    callback,
    disconnect,
    catalog as catalog_settings,
    store_for,
    telegram_status,
    telegram_start_oauth,
    telegram_disconnect,
)

# Register built-in providers (Slack, …).
from . import providers as _providers  # noqa: F401

__all__ = [
    # registry
    "ConnectionProvider",
    "connection_provider",
    "register",
    "resolve",
    "catalog",
    "get",
    # store
    "ConnectionStore",
    # client apps
    "ClientApp",
    "AmbiguousClientApp",
    "list_client_apps",
    "resolve_client_app",
    "client_app_secret",
    "oauth_state_secret",
    # oauth
    "ProviderHttpError",
    "build_authorize_url",
    "callback_url",
    "exchange_code",
    "refresh_access_token",
    # settings ops
    "configure_connections",
    "status",
    "start_oauth",
    "callback",
    "disconnect",
    "catalog_settings",
    "store_for",
    "telegram_status",
    "telegram_start_oauth",
    "telegram_disconnect",
]
