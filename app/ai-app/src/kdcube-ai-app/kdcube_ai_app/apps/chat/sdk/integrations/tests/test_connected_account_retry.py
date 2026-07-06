# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Live provider-rejection recovery contract (refresh-retry-once)."""

from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.sdk.integrations import connected_accounts as ca
from kdcube_ai_app.apps.chat.sdk.integrations.connected_accounts import (
    ConnectedAccountCredential,
    connected_account_auth_failure,
    run_with_connected_account_retry,
)


def _credential(*, ok: bool = True, token: str = "tok-1") -> ConnectedAccountCredential:
    return ConnectedAccountCredential(
        ok=ok,
        access_token=token if ok else "",
        account_id="acct-1",
        provider_id="google",
        connector_app_id="gmail",
        claim="gmail:read",
        tool_name="gmail.search_gmail",
        tenant="demo-tenant",
        project="demo-project",
    )


@pytest.mark.asyncio
async def test_retry_runner_passes_success_through(monkeypatch):
    async def _boom(*_a, **_kw):  # neither refresh nor marking may run
        raise AssertionError("no recovery path should be taken on success")

    monkeypatch.setattr(ca, "refresh_connected_account_claim", _boom)
    monkeypatch.setattr(ca, "provider_auth_failed", _boom)

    async def run():
        return {"ok": True, "ret": {"count": 3}}

    result = await run_with_connected_account_retry({}, where="gmail.search_gmail", run=run)
    assert result == {"ok": True, "ret": {"count": 3}}


@pytest.mark.asyncio
async def test_retry_runner_refreshes_once_and_succeeds(monkeypatch):
    calls = {"run": 0, "refresh": 0}

    async def fake_refresh(_source, *, credential):
        calls["refresh"] += 1
        assert credential.account_id == "acct-1"
        return _credential(token="tok-2")

    monkeypatch.setattr(ca, "refresh_connected_account_claim", fake_refresh)

    async def run():
        calls["run"] += 1
        if calls["run"] == 1:
            return connected_account_auth_failure(_credential(), "invalid_grant")
        return {"ok": True, "ret": {"count": 1}}

    result = await run_with_connected_account_retry({}, where="gmail.search_gmail", run=run)
    assert result == {"ok": True, "ret": {"count": 1}}
    assert calls == {"run": 2, "refresh": 1}


@pytest.mark.asyncio
async def test_retry_runner_unrefreshable_returns_reconnect_envelope(monkeypatch):
    failed = _credential(ok=False)

    async def fake_refresh(_source, *, credential):
        return ConnectedAccountCredential(
            ok=False,
            account_id=credential.account_id,
            provider_id=credential.provider_id,
            connector_app_id=credential.connector_app_id,
            claim=credential.claim,
            tool_name=credential.tool_name,
            tenant=credential.tenant,
            project=credential.project,
            error_payload={
                "ok": False,
                "error": {"code": "needs_connected_account_consent", "message": "Reconnect."},
                "consent": {"reason": "reconnect_required", "url": "/hub", "retry_hint": True},
            },
        )

    monkeypatch.setattr(ca, "refresh_connected_account_claim", fake_refresh)

    runs = {"count": 0}

    async def run():
        runs["count"] += 1
        return connected_account_auth_failure(failed, "token_revoked")

    result = await run_with_connected_account_retry({}, where="slack.search_slack", run=run)
    assert runs["count"] == 1  # unrefreshable: no second provider round-trip
    assert result["ok"] is False
    assert result["error"]["code"] == "needs_connected_account_consent"
    assert result["consent"]["reason"] == "reconnect_required"


@pytest.mark.asyncio
async def test_retry_runner_second_rejection_marks_and_reports(monkeypatch):
    marked = {}

    async def fake_refresh(_source, *, credential):
        return _credential(token="tok-2")

    async def fake_failed(_source, *, credential, where, provider_error):
        marked.update(
            account_id=credential.account_id,
            where=where,
            provider_error=provider_error,
        )
        return {"ok": False, "error": {"code": "needs_connected_account_consent"}}

    monkeypatch.setattr(ca, "refresh_connected_account_claim", fake_refresh)
    monkeypatch.setattr(ca, "provider_auth_failed", fake_failed)

    async def run():
        return connected_account_auth_failure(_credential(), "still rejected")

    result = await run_with_connected_account_retry({}, where="gmail.send_gmail", run=run)
    assert result["ok"] is False
    assert marked == {
        "account_id": "acct-1",
        "where": "gmail.send_gmail",
        "provider_error": "still rejected",
    }


def test_auth_failure_marker_shape_is_internal():
    marker = connected_account_auth_failure(_credential(), "invalid_auth")
    assert set(marker) == {"__connected_account_auth_failure__"}
    assert marker["__connected_account_auth_failure__"]["message"] == "invalid_auth"
