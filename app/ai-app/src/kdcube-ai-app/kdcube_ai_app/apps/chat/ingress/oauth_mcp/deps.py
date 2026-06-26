# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

"""
Per-request dependency resolution for the OAuth2 AS / MCP routes.

Each dependency prefers an override on ``app.state`` (set by tests) and otherwise
builds the real platform-backed implementation lazily:

- session authentication via :class:`BundleSessionAuthManager` (validates the
  opaque ``kst1`` token against the Redis user record);
- the :class:`GrantStore` on the platform Redis client.

The OAuth tenant/project (which session namespace the consenting admin belongs
to) and the auth cookie name are configurable via environment.
"""
from __future__ import annotations

import os
from typing import Any, Awaitable, Callable, Optional

from fastapi import Request

AuthenticateFn = Callable[[str], Awaitable[Optional[dict]]]

# Roles permitted to authorize an integration connection.
ADMIN_ROLES = {"kdcube:role:super-admin"}


def oauth_tenant_project() -> tuple[str, str]:
    return (
        os.environ.get("KDCUBE_OAUTH_TENANT", "home"),
        os.environ.get("KDCUBE_OAUTH_PROJECT", "demo"),
    )


def get_authenticate(request: Request) -> AuthenticateFn:
    fn = getattr(request.app.state, "oauth_authenticate", None)
    if fn is not None:
        return fn

    from kdcube_ai_app.auth.bundle import BundleSessionAuthManager, get_bundle_session_authority

    tenant, project = oauth_tenant_project()
    authority = get_bundle_session_authority(tenant=tenant, project=project)
    manager = BundleSessionAuthManager(authority=authority)

    async def _authenticate(token: str) -> Optional[dict]:
        try:
            user = await manager.authenticate(token)
        except Exception:
            return None
        return {"sub": user.sub, "roles": list(user.roles or [])}

    return _authenticate


def get_grant_store(request: Request) -> Any:
    store = getattr(request.app.state, "oauth_grant_store", None)
    if store is not None:
        return store

    from kdcube_ai_app.apps.chat.sdk.config import get_settings
    from kdcube_ai_app.infra.redis.client import get_async_redis_client

    from .store import GrantStore

    tenant, project = oauth_tenant_project()
    redis = get_async_redis_client(get_settings().REDIS_URL)
    return GrantStore(redis, tenant, project)


def get_access_token_minter(request: Request) -> Callable[[str, list], Awaitable[dict]]:
    """Returns ``async (sub, scopes) -> {access_token, expires_in}``.

    Production mints a short-lived read-only integration session (the
    ``feedback-reader`` grant); see :mod:`grants`.
    """
    fn = getattr(request.app.state, "oauth_mint_access_token", None)
    if fn is not None:
        return fn

    from .grants import mint_feedback_reader_access_token

    return mint_feedback_reader_access_token


def extract_bearer(request: Request) -> Optional[str]:
    """The admin's session token: Authorization bearer first, then auth cookie."""
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    cookie_name = os.environ.get("KDCUBE_AUTH_COOKIE", "__Secure-LATC")
    return request.cookies.get(cookie_name)


def is_admin(roles) -> bool:
    return bool(set(roles or []) & ADMIN_ROLES)
