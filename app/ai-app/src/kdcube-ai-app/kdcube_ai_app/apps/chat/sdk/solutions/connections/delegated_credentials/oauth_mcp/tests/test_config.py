# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_credentials.oauth_mcp.tests.helpers import mount_test_oauth_adapter
from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_credentials.oauth_mcp.clients import dcr_redirect_allowed, get_client
from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_credentials.oauth_mcp.config import oauth_mcp_config


def test_oauth_mcp_routes_are_descriptor_gated():
    app = FastAPI()
    mount_test_oauth_adapter(app)

    response = TestClient(app).get("/.well-known/oauth-authorization-server")

    assert response.status_code == 404


def test_oauth_mcp_reads_explicit_connection_hub_mount_config():
    app = FastAPI()
    app.state.oauth_mcp_config = {
        "enabled": True,
        "issuer": "https://mcp.example.test",
        "tenant": "tenant-a",
        "project": "project-b",
        "auth_cookie_name": "__Secure-KDCUBE",
        "public_clients": [
            {
                "client_id": "local-client",
                "redirect_uris": ["http://localhost/callback"],
            },
        ],
        "dynamic_client_registration": {
            "allowed_redirect_uris": ["https://allowed.example.test/callback"],
        },
    }
    mount_test_oauth_adapter(app)

    cfg = oauth_mcp_config(app)
    assert cfg.enabled is True
    assert cfg.issuer == "https://mcp.example.test"
    assert cfg.tenant == "tenant-a"
    assert cfg.project == "project-b"
    assert cfg.auth_cookie_name == "__Secure-KDCUBE"
    assert cfg.brand == "KDCube"  # default when oauth_mcp brand is unset

    assert get_client("local-client", app) is not None
    assert get_client("claude", app) is None
    assert dcr_redirect_allowed("https://allowed.example.test/callback", app)
    assert not dcr_redirect_allowed("https://claude.ai/api/mcp/auth_callback", app)

    response = TestClient(app).get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200
    assert response.json()["issuer"] == "https://mcp.example.test"


def test_oauth_mcp_brand_defaults_to_kdcube():
    app = FastAPI()
    app.state.oauth_mcp_config = {"enabled": True}
    assert oauth_mcp_config(app).brand == "KDCube"


def test_oauth_mcp_brand_from_descriptor_is_reflected():
    app = FastAPI()
    app.state.oauth_mcp_config = {"enabled": True, "brand": "Acme AI"}
    assert oauth_mcp_config(app).brand == "Acme AI"


def test_oauth_mcp_parses_resource_capabilities_and_tools():
    app = FastAPI()
    app.state.oauth_mcp_config = {
        "enabled": True,
        "capabilities": [
            {
                "grant": "memories:read",
                "label": "Read memories",
                "delegable_roles": ["kdcube:role:chat-user"],
            },
            {
                "grant": "memories:maintain",
                "label": "Maintain memories",
                "delegable_roles": ["kdcube:role:privileged"],
            },
        ],
        "resources": [
            {
                "resource": "https://runtime.example.test/*/public/mcp/memories",
                "tools": {
                    "memory_search": {
                        "label": "Search memories",
                        "grants": ["memories:read"],
                    },
                    "memory_reconcile": {
                        "label": "Reconcile memories",
                        "grants": ["memories:read", "memories:maintain"],
                    },
                },
            },
        ],
    }
    cfg = oauth_mcp_config(app)

    assert cfg.supported_scopes("https://runtime.example.test/x/public/mcp/memories") == (
        "memories:read",
        "memories:maintain",
    )
    assert [tool.name for tool in cfg.tools_for_scopes(["memories:read"], resource="https://runtime.example.test/x/public/mcp/memories")] == ["memory_search"]
    assert [
        tool.name
        for tool in cfg.tools_for_scopes(
            ["memories:read", "memories:maintain"],
            resource="https://runtime.example.test/x/public/mcp/memories",
        )
    ] == ["memory_search", "memory_reconcile"]
