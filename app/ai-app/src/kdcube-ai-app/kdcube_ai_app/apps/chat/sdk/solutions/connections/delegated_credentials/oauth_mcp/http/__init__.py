# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""HTTP adapter pieces for Connection Hub delegated OAuth credentials."""

from .discovery import (
    resolve_issuer,
    router as discovery_router,
    unauthorized_challenge,
    well_known_authorization_server,
    well_known_protected_resource,
)
from .routes import (
    authorize,
    authorize_consent,
    register_client,
    router as oauth_router,
    token,
)

__all__ = [
    "authorize",
    "authorize_consent",
    "discovery_router",
    "oauth_router",
    "register_client",
    "resolve_issuer",
    "token",
    "unauthorized_challenge",
    "well_known_authorization_server",
    "well_known_protected_resource",
]
