# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""get_authenticate must accept BOTH oauth_mcp token kinds, bundle authority first.

oauth_mcp authenticates two distinct tokens:
  - the integration ACCESS token at /mcp — a STATEFUL platform bundle kst1
    (roles in the Redis user record), and
  - the admin's web-login session at /oauth/authorize — validated by the gateway's
    configured manager (a stateless token carrying roles in its claims).

Both share the kst1 schema, so the gateway's custom verifier will ACCEPT the
access token but read empty roles from its (role-less) claims -> 403. The bundle
authority must therefore be tried FIRST. The app.state override still wins.
"""
from __future__ import annotations

import types

import pytest

from kdcube_ai_app.apps.chat.ingress.oauth_mcp import deps


def _request_without_override():
    state = types.SimpleNamespace()  # no oauth_authenticate attribute
    app = types.SimpleNamespace(state=state)
    return types.SimpleNamespace(app=app)


def _patch_managers(monkeypatch, gateway, bundle_manager):
    import kdcube_ai_app.apps.chat.ingress.resolvers as resolvers
    import kdcube_ai_app.auth.bundle as bundle

    monkeypatch.setattr(resolvers, "create_auth_manager", lambda *a, **k: gateway)
    monkeypatch.setattr(bundle, "BundleSessionAuthManager", lambda *a, **k: bundle_manager)
    monkeypatch.setattr(bundle, "get_bundle_session_authority", lambda *a, **k: object())


class _WebUser:
    sub = "google:admin@example.test"
    roles = ["kdcube:role:super-admin"]


class _IntegrationUser:
    sub = "integration:claude:google:admin@example.test"
    roles = ["kdcube:role:feedback-reader"]


class _RolelessUser:
    sub = "integration:claude:google:admin@example.test"
    roles = []  # the bug: gateway accepts the access token but loses its roles


class _GreedyGatewayManager:
    """Custom session manager: validates the web token, AND (the bug) ACCEPTS the
    integration access token but with EMPTY roles (shared schema, no roles in claims)."""
    async def authenticate(self, token: str):
        if token == "web-session":
            return _WebUser()
        if token == "integration-access":
            return _RolelessUser()
        raise ValueError("unknown token")


class _BundleManager:
    """Platform bundle authority: validates the integration access token with its
    real roles, and REJECTS the stateless web token (no Redis session record)."""
    async def authenticate(self, token: str):
        if token == "integration-access":
            return _IntegrationUser()
        raise ValueError("no bundle session")


async def test_access_token_resolves_feedback_reader_not_empty_roles(monkeypatch):
    # Regression: the bundle authority is tried first, so the access token keeps its
    # feedback-reader role instead of the gateway's empty-roles result (-> 403).
    _patch_managers(monkeypatch, _GreedyGatewayManager(), _BundleManager())
    authenticate = deps.get_authenticate(_request_without_override())
    assert await authenticate("integration-access") == {
        "sub": "integration:claude:google:admin@example.test",
        "roles": ["kdcube:role:feedback-reader"],
    }


async def test_web_session_falls_through_to_gateway(monkeypatch):
    _patch_managers(monkeypatch, _GreedyGatewayManager(), _BundleManager())
    authenticate = deps.get_authenticate(_request_without_override())
    assert await authenticate("web-session") == {
        "sub": "google:admin@example.test",
        "roles": ["kdcube:role:super-admin"],
    }


async def test_unknown_token_fails_closed(monkeypatch):
    _patch_managers(monkeypatch, _GreedyGatewayManager(), _BundleManager())
    authenticate = deps.get_authenticate(_request_without_override())
    assert await authenticate("garbage") is None


async def test_app_state_override_takes_precedence():
    async def _override(token):
        return {"sub": "overridden", "roles": []}

    state = types.SimpleNamespace(oauth_authenticate=_override)
    app = types.SimpleNamespace(state=state)
    request = types.SimpleNamespace(app=app)

    authenticate = deps.get_authenticate(request)
    assert await authenticate("anything") == {"sub": "overridden", "roles": []}
