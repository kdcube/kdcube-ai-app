from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

import pytest

from kdcube_ai_app.apps.chat.sdk.integrations.connections import oauth as conn_oauth
from kdcube_ai_app.apps.chat.sdk.integrations.connections import registry as conn_registry

# Importing the package registers the built-in providers (slack, google).
import kdcube_ai_app.apps.chat.sdk.integrations.connections  # noqa: F401


# ── a tiny fake httpx.AsyncClient that records the last POST and returns canned data


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self.reason_phrase = "OK" if status_code < 400 else "ERR"
        import json as _json

        self.text = _json.dumps(payload)


class _FakeAsyncClient:
    last_post: dict[str, Any] = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, *, data=None, headers=None):
        _FakeAsyncClient.last_post = {"url": url, "data": dict(data or {}), "headers": dict(headers or {})}
        return _FakeResponse(
            status_code=_FakeAsyncClient.response_status,
            payload=_FakeAsyncClient.response_payload,
        )


@pytest.fixture
def fake_httpx(monkeypatch):
    _FakeAsyncClient.response_status = 200
    _FakeAsyncClient.response_payload = {}
    _FakeAsyncClient.last_post = {}
    monkeypatch.setattr(conn_oauth.httpx, "AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient


@pytest.mark.asyncio
async def test_refresh_access_token_posts_refresh_grant(fake_httpx):
    fake_httpx.response_payload = {"access_token": "ya29.new", "expires_in": 3599, "token_type": "Bearer"}
    prov = conn_registry.resolve("google")
    token = await conn_oauth.refresh_access_token(
        prov, refresh_token="rt-123", client_id="cid", client_secret="sec",
    )
    sent = fake_httpx.last_post
    assert sent["url"] == prov.token_url
    assert sent["data"]["grant_type"] == "refresh_token"
    assert sent["data"]["refresh_token"] == "rt-123"
    assert sent["data"]["client_id"] == "cid"
    assert token["access_token"] == "ya29.new"
    # expires_in → expires_at (epoch) derived, in the near future
    assert int(token["expires_at"]) > int(time.time())
    # Google omits a new refresh_token on refresh → not present here (caller preserves).
    assert "refresh_token" not in token


@pytest.mark.asyncio
async def test_refresh_access_token_requires_refresh_token(fake_httpx):
    prov = conn_registry.resolve("google")
    with pytest.raises(ValueError):
        await conn_oauth.refresh_access_token(prov, refresh_token="", client_id="cid", client_secret="sec")


@pytest.mark.asyncio
async def test_refresh_access_token_raises_on_http_error(fake_httpx):
    fake_httpx.response_status = 400
    fake_httpx.response_payload = {"error": "invalid_grant", "error_description": "Token has been revoked."}
    prov = conn_registry.resolve("google")
    with pytest.raises(conn_oauth.ProviderHttpError):
        await conn_oauth.refresh_access_token(prov, refresh_token="rt", client_id="cid", client_secret="sec")


# ── build_authorize_url merges authorize_extra_params (offline access) ─────────


@pytest.mark.asyncio
async def test_build_authorize_url_merges_extra_params(monkeypatch):
    from kdcube_ai_app.apps.chat.sdk.integrations.connections.apps import ClientApp
    from kdcube_ai_app.apps.chat.sdk.integrations.connections.store import ConnectionStore
    from kdcube_ai_app.apps.chat.sdk.integrations.connections import store as conn_store
    from kdcube_ai_app.apps.chat.sdk.integrations.connections import apps as conn_apps

    async def _empty_get_secret(*args, **kwargs):
        return ""

    monkeypatch.setattr(conn_store, "get_secret", _empty_get_secret)
    monkeypatch.setattr(conn_apps, "get_secret", _empty_get_secret)

    ep = SimpleNamespace(
        bundle_prop=lambda key, default=None: {
            "connections.oauth_state_secret": "sek",
            "connections.oauth.public_base_url": "https://host.test",
        }.get(key, default),
        bundle_id="b@1",
        config=SimpleNamespace(ai_bundle_spec=SimpleNamespace(id="b@1")),
        settings=SimpleNamespace(TENANT="t", PROJECT="p"),
        comm_context=SimpleNamespace(actor=SimpleNamespace(tenant_id="t", project_id="p")),
    )

    prov = conn_registry.resolve("google")
    app = ClientApp(app_id="gmail", provider="google", client_id="cid", scopes=("openid", "email"))
    store = ConnectionStore("/tmp/conn-test-authorize", user_id="u1", bundle_id="b@1")
    result = await conn_oauth.build_authorize_url(prov, app, entrypoint=ep, store=store)
    url = result["authorize_url"]
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "include_granted_scopes=true" in url
