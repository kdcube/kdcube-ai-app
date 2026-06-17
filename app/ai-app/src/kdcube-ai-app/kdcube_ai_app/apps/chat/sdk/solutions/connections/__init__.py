# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Public `connections` named-service contract (OAuth integrations).

The transport-neutral contract for letting a user connect external systems and
for other bundles to fetch the user's access token. A bundle implements
``ConnectionsProviderBase`` against its chosen storage; consumers use
``ConnectionsClient`` over the local or API transport.

See docs/sdk/integrations/connections-README.md for the design.
"""

from __future__ import annotations

from .contract import (
    NAMESPACE,
    CONNECTION_CATALOG,
    CONNECTION_STATUS,
    CONNECTION_GET_TOKEN,
    CONNECTION_DISCONNECT,
    OAUTH_START,
    CONNECTION_OPERATIONS,
    build_connection_operations,
    Connection,
    ConnectionToken,
    CatalogEntry,
    ClientApp,
    AmbiguousConnectionAccount,
)
from .provider import ConnectionsProviderBase
from .client import ConnectionsClient, ConnectionsError

__all__ = [
    "NAMESPACE",
    "CONNECTION_CATALOG",
    "CONNECTION_STATUS",
    "CONNECTION_GET_TOKEN",
    "CONNECTION_DISCONNECT",
    "OAUTH_START",
    "CONNECTION_OPERATIONS",
    "build_connection_operations",
    "Connection",
    "ConnectionToken",
    "CatalogEntry",
    "ClientApp",
    "AmbiguousConnectionAccount",
    "ConnectionsProviderBase",
    "ConnectionsClient",
    "ConnectionsError",
]
