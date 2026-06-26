# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

"""
Public OAuth client registry.

Claude Code is pre-registered as a public client (no secret,
``token_endpoint_auth_method = none``). Redirect-URI matching follows RFC 8252:
the loopback redirects (``localhost`` / ``127.0.0.1``) match on any port because
the native client binds a dynamic local port for its callback; all other
redirects must match exactly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import urlsplit

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Redirect URIs a dynamically-registered (RFC 7591) client may register. DCR is
# open (it runs before the user authenticates), so without this an attacker could
# register a client pointing at their own server. Restricting it to claude.ai's
# MCP callback + loopback (any port, matched by redirect_uri_allowed) means a
# stolen auth code can only reach claude.ai or the victim's own machine.
# Override with KDCUBE_OAUTH_DCR_REDIRECT_URIS (comma-separated).
_DEFAULT_DCR_REDIRECTS = (
    "https://claude.ai/api/mcp/auth_callback",
    "http://localhost/callback",
    "http://127.0.0.1/callback",
)


@dataclass(frozen=True)
class PublicClient:
    client_id: str
    redirect_uris: Tuple[str, ...]
    token_endpoint_auth_method: str = "none"


def client_from_record(record: dict) -> "PublicClient":
    """Build a PublicClient from a stored DCR registration record."""
    return PublicClient(
        client_id=record["client_id"],
        redirect_uris=tuple(record.get("redirect_uris") or ()),
        token_endpoint_auth_method=record.get("token_endpoint_auth_method", "none"),
    )


CLAUDE_CLIENT = PublicClient(
    client_id="claude",
    redirect_uris=(
        "http://localhost/callback",
        "http://127.0.0.1/callback",
        "https://claude.ai/api/mcp/auth_callback",
    ),
)

_REGISTRY = {CLAUDE_CLIENT.client_id: CLAUDE_CLIENT}


def get_client(client_id: str) -> Optional[PublicClient]:
    return _REGISTRY.get(client_id)


def _dcr_allowed_redirects() -> Tuple[str, ...]:
    env = os.environ.get("KDCUBE_OAUTH_DCR_REDIRECT_URIS")
    if env:
        return tuple(u.strip() for u in env.split(",") if u.strip())
    return _DEFAULT_DCR_REDIRECTS


def dcr_redirect_allowed(uri: str) -> bool:
    """True iff ``uri`` is a permitted redirect for dynamic client registration."""
    allowlist = PublicClient(client_id="__dcr__", redirect_uris=_dcr_allowed_redirects())
    return redirect_uri_allowed(allowlist, uri)


def redirect_uri_allowed(client: Optional[PublicClient], uri: str) -> bool:
    if client is None or not uri:
        return False
    if uri in client.redirect_uris:
        return True
    got = urlsplit(uri)
    if got.hostname in _LOOPBACK_HOSTS:
        for allowed in client.redirect_uris:
            a = urlsplit(allowed)
            if (
                a.hostname in _LOOPBACK_HOSTS
                and a.hostname == got.hostname
                and a.scheme == got.scheme
                and a.path == got.path
            ):
                return True
    return False
