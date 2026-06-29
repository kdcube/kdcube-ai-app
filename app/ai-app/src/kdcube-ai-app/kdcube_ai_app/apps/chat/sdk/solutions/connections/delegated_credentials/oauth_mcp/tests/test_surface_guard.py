# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_credentials.oauth_mcp import (
    surface_guard,
)

GUARD_RESOURCE = "http://testserver/guard"


class _GrantStore:
    def __init__(self, record=None):
        self.record = record

    async def get_access_grant_record(self, access_token: str):
        return self.record


def _authority(scopes=None, *, resource=GUARD_RESOURCE):
    return {
        "schema": "kdcube.credential.v1",
        "credential_kind": "delegated_client_access",
        "issuer_authority_id": "oauth_mcp",
        "issuer_authenticator_id": "oauth_mcp.bearer",
        "subject": "integration:claude:admin",
        "audience": "kdcube:mcp",
        "attrs": {
            "scopes": list(scopes or ["conversations:read"]),
            "resource": resource,
        },
    }


def _memory_authority():
    return _authority(scopes=["memories:read"])


def _rpc_tool_call(name="conversations_export", rpc_id=1):
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": {}},
    }


def test_mcp_auth_mode_keeps_bundle_owned_header_metadata_unmanaged():
    auth = {"header_name": "X-Knowledge-MCP-Token"}

    assert surface_guard.mcp_auth_mode(auth) == ""
    assert surface_guard.managed_mcp_auth_policy(auth) is None


def test_managed_policy_parses_per_tool_grants():
    policy = surface_guard.managed_mcp_auth_policy({
        "mode": "managed",
        "authority_id": "oauth_mcp",
        "tools": {
            "conversations_export": {
                "grants": ["conversations:read"],
            },
        },
    })

    assert policy is not None
    assert policy.authority_id == "oauth_mcp"
    assert policy.tool_policies is not None
    assert policy.tool_policies["conversations_export"].grants == ("conversations:read",)


def test_extract_mcp_tool_calls_handles_batch():
    calls = surface_guard.extract_mcp_tool_calls(
        b"""[
          {"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}},
          {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"conversations_export"}}
        ]"""
    )

    assert calls == [(2, "conversations_export")]


def _client(monkeypatch, *, grant_record, auth=None, user=None):
    async def fake_authenticate(token: str):
        if token != "reader":
            return None
        return user or {
            "sub": "integration:claude:admin",
            "roles": ["kdcube:role:feedback-reader"],
            "permissions": ["kdcube:*:conversations:*;read"],
        }

    monkeypatch.setattr(
        surface_guard,
        "_authenticate_oauth_mcp_access_token",
        fake_authenticate,
    )

    app = FastAPI()
    app.state.oauth_grant_store = _GrantStore(grant_record)
    auth = auth or {
        "mode": "managed",
        "authority_id": "oauth_mcp",
        "tools": {
            "conversations_export": {
                "grants": ["conversations:read"],
            },
        },
        "selected_tool_grants": True,
    }

    @app.post("/guard")
    async def guard(request: Request):
        body = await request.body()
        denial = await surface_guard.authorize_delegated_mcp_request(
            request=request,
            body=body,
            auth=auth,
        )
        return denial or JSONResponse({"ok": True})

    return TestClient(app)


def test_managed_guard_allows_consented_tool(monkeypatch):
    client = _client(
        monkeypatch,
        grant_record={
            "tools": ["conversations_export"],
            "authority": _authority(),
        },
    )

    response = client.post(
        "/guard",
        json=_rpc_tool_call(),
        headers={"Authorization": "Bearer reader"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_managed_guard_allows_configured_non_feedback_tool(monkeypatch):
    client = _client(
        monkeypatch,
        auth={
            "mode": "managed",
            "authority_id": "oauth_mcp",
            "tools": {
                "memory_search": {
                    "grants": ["memories:read"],
                },
            },
            "selected_tool_grants": True,
        },
        user={
            "sub": "integration:claude:user",
            "roles": ["kdcube:role:delegated-client"],
            "permissions": ["memories:read"],
        },
        grant_record={
            "tools": ["memory_search"],
            "authority": _memory_authority(),
        },
    )

    response = client.post(
        "/guard",
        json=_rpc_tool_call(name="memory_search"),
        headers={"Authorization": "Bearer reader"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_managed_guard_enforces_grants_per_called_tool(monkeypatch):
    client = _client(
        monkeypatch,
        auth={
            "mode": "managed",
            "authority_id": "oauth_mcp",
            "tools": {
                "memory_search": {"grants": ["memories:read"]},
                "memory_delete": {"grants": ["memories:write"]},
            },
            "selected_tool_grants": True,
        },
        user={
            "sub": "integration:claude:user",
            "roles": ["kdcube:role:delegated-client"],
            "permissions": ["memories:read"],
        },
        grant_record={
            "tools": ["memory_search", "memory_delete"],
            "authority": _memory_authority(),
        },
    )

    response = client.post(
        "/guard",
        json=_rpc_tool_call(name="memory_delete"),
        headers={"Authorization": "Bearer reader"},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert "required delegated grant is missing for tool: memory_delete" in result["content"][0]["text"]


def test_managed_guard_fails_closed_when_tool_not_consented(monkeypatch):
    client = _client(
        monkeypatch,
        grant_record={
            "tools": [],
            "authority": _authority(),
        },
    )

    response = client.post(
        "/guard",
        json=_rpc_tool_call(),
        headers={"Authorization": "Bearer reader"},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert "not consented" in result["content"][0]["text"]


def test_managed_guard_rejects_resource_mismatch(monkeypatch):
    client = _client(
        monkeypatch,
        grant_record={
            "tools": ["conversations_export"],
            "authority": _authority(resource="http://testserver/other"),
        },
    )

    response = client.post(
        "/guard",
        json=_rpc_tool_call(),
        headers={"Authorization": "Bearer reader"},
    )

    assert response.status_code == 403
    assert response.json()["error_description"] == "delegated credential resource mismatch"


def test_managed_guard_rejects_missing_resource(monkeypatch):
    authority = _authority()
    authority["attrs"].pop("resource")
    client = _client(
        monkeypatch,
        grant_record={
            "tools": ["conversations_export"],
            "authority": authority,
        },
    )

    response = client.post(
        "/guard",
        json=_rpc_tool_call(),
        headers={"Authorization": "Bearer reader"},
    )

    assert response.status_code == 403
    assert response.json()["error_description"] == "delegated credential resource is missing"


def test_managed_guard_requires_bearer(monkeypatch):
    client = _client(
        monkeypatch,
        grant_record={
            "tools": ["conversations_export"],
            "authority": _authority(),
        },
    )

    response = client.post("/guard", json=_rpc_tool_call())

    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"
