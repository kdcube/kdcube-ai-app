# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Test helpers for the Connection Hub delegated credential OAuth adapter."""
from __future__ import annotations

from fastapi import FastAPI

from kdcube_ai_app.apps.chat.sdk.solutions.connections.authority_registry import AuthorityRegistry
from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_credentials.oauth_mcp.authority import OAuthMcpAuthorityProvider
from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_credentials.oauth_mcp.config import oauth_mcp_config
from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_credentials.oauth_mcp.http.discovery import router as discovery_router
from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_credentials.oauth_mcp.http.routes import router as oauth_routes_router


def enable_oauth_mcp(app: FastAPI, *, issuer: str = "https://yey.boats") -> None:
    app.state.oauth_mcp_config = {
        "enabled": True,
        "issuer": issuer,
    }


def mount_test_oauth_adapter(app: FastAPI) -> FastAPI:
    """Mount OAuth adapter routes for tests only.

    Production exposure is the Connection Hub bundle public ``oauth`` operation,
    not an ingress package alias.
    """
    if not oauth_mcp_config(app).enabled:
        return app
    registry = getattr(app.state, "connection_hub_authority_registry", None)
    if registry is None:
        registry = AuthorityRegistry()
        app.state.connection_hub_authority_registry = registry
    if registry.get("oauth_mcp") is None:
        registry.register(OAuthMcpAuthorityProvider())
    app.include_router(discovery_router, tags=["oauth-mcp discovery"])
    app.include_router(oauth_routes_router, tags=["oauth-mcp authorize"])
    return app
