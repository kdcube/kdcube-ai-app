"""Callback error pages: provider-denied OAuth must land on an explanatory page.

Surfaced case: a user whose Slack workspace lacks the app clicks Connect and
Slack bounces back with an error code — the page must diagnose it in plain
words (naming the provider from the state), carry the provider's own message,
state that nothing was connected, and offer a way back.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

# Importing the package registers the built-in providers (slack, google).
import kdcube_ai_app.apps.chat.sdk.integrations.connections  # noqa: F401
from kdcube_ai_app.apps.chat.sdk.integrations.connections import settings as conn_settings
from kdcube_ai_app.apps.chat.sdk.integrations.connections.store import ConnectionStore, _b64url_json


def _unsigned_state(provider: str = "slack") -> str:
    # Signature never verifies — good: the error page must still name the provider
    # (peek is display-only) while refusing to trust anything else from the state.
    return _b64url_json({"v": 1, "provider": provider}) + ".bogus-signature"


def _body(resp) -> str:
    return resp.body.decode("utf-8")


@pytest.mark.asyncio
async def test_access_denied_names_provider_and_offers_retry():
    resp = await conn_settings.callback(
        SimpleNamespace(), state=_unsigned_state("slack"), error="access_denied"
    )
    body = _body(resp)
    assert "declined on Slack" in body
    assert "Nothing was connected." in body
    assert "Connections settings" in body
    assert 'class="err"' in body


@pytest.mark.asyncio
async def test_non_distributed_slack_app_explains_workspace_gap():
    resp = await conn_settings.callback(
        SimpleNamespace(),
        state=_unsigned_state("slack"),
        error="invalid_team_for_non_distributed_app",
    )
    body = _body(resp)
    assert "home workspace" in body
    assert "distribution" in body


@pytest.mark.asyncio
async def test_unknown_error_code_still_shows_the_code():
    resp = await conn_settings.callback(
        SimpleNamespace(), state=_unsigned_state("google"), error="some_new_provider_code"
    )
    body = _body(resp)
    assert "some_new_provider_code" in body
    assert "Gmail" in body  # the google provider's display label
    assert "Nothing was connected." in body


@pytest.mark.asyncio
async def test_error_description_is_quoted_on_the_page():
    resp = await conn_settings.callback(
        SimpleNamespace(),
        state=_unsigned_state("slack"),
        error="invalid_scope",
        error_description="scope chat:write is not allowed",
    )
    body = _body(resp)
    assert "Provider message" in body
    assert "scope chat:write is not allowed" in body


@pytest.mark.asyncio
async def test_missing_state_falls_back_to_generic_provider_wording():
    resp = await conn_settings.callback(SimpleNamespace(), state="", error="access_denied")
    body = _body(resp)
    assert "The provider" in body
    assert "Nothing was connected." in body


@pytest.mark.asyncio
async def test_signed_return_hint_becomes_the_return_link(tmp_path, monkeypatch):
    store = ConnectionStore(tmp_path, user_id="u1")
    issued = await store.create_oauth_state_async(
        provider="slack",
        secret="s3cret",
        source="kdcube_widget",
        app_id="a1",
        return_hint="https://app.example/settings/connections",
    )

    monkeypatch.setattr(conn_settings, "_storage_root", lambda ep: tmp_path)

    async def _secret(ep):
        return "s3cret"

    monkeypatch.setattr(conn_settings, "oauth_state_secret", _secret)

    resp = await conn_settings.callback(
        SimpleNamespace(), state=issued["state"], error="access_denied"
    )
    body = _body(resp)
    assert "https://app.example/settings/connections" in body
    assert "Return to app" in body

    # single-use: the same state does not resolve a link twice
    resp2 = await conn_settings.callback(
        SimpleNamespace(), state=issued["state"], error="access_denied"
    )
    assert "https://app.example/settings/connections" not in _body(resp2)


@pytest.mark.asyncio
async def test_non_https_return_hint_is_rejected(tmp_path, monkeypatch):
    store = ConnectionStore(tmp_path, user_id="u1")
    issued = await store.create_oauth_state_async(
        provider="slack",
        secret="s3cret",
        source="kdcube_widget",
        app_id="a1",
        return_hint="javascript:alert(1)",
    )

    monkeypatch.setattr(conn_settings, "_storage_root", lambda ep: tmp_path)

    async def _secret(ep):
        return "s3cret"

    monkeypatch.setattr(conn_settings, "oauth_state_secret", _secret)

    resp = await conn_settings.callback(
        SimpleNamespace(), state=issued["state"], error="access_denied"
    )
    body = _body(resp)
    assert "javascript:alert(1)" not in body
    assert "Connections settings" in body
