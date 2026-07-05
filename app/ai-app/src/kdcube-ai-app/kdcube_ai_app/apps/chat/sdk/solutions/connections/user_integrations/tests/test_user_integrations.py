# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

from typing import Any

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions import connections
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations import (
    ConnectedAccount,
    MemoryOAuthStateStore,
    UserIntegrationBroker,
    UserIntegrationStore,
    operations_for_user,
    user_integrations_config,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.adapters import (
    UserIntegrationAdapter,
    register_adapter,
    resolve_adapter,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.store import credential_id_for
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations import store as ui_store


def _sample_config():
    return user_integrations_config(
        {
            "user_integrations": {
                "enabled": True,
                "providers": {
                    "google": {
                        "label": "Google",
                        "adapter": "google.oauth",
                        "capabilities": {
                            "gmail:read": {
                                "label": "Read Gmail",
                                "description": "Read Gmail messages for this user.",
                                "provider_scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
                            },
                            "gmail:send": {
                                "label": "Send Gmail",
                                "provider_scopes": ["https://www.googleapis.com/auth/gmail.send"],
                            },
                        },
                        "connector_apps": {
                            "gmail": {
                                "label": "Gmail connector",
                                "client_id": "client-id",
                                "client_secret_ref": "integrations.google.gmail.client_secret",
                                "capability_ceiling": ["gmail:read", "gmail:send"],
                            }
                        },
                    }
                },
            }
        }
    )


class _FakeOAuthAdapter(UserIntegrationAdapter):
    adapter_id = "test.oauth"
    label = "Test OAuth"
    kind = "oauth2"
    authorize_url = "https://provider.example.test/oauth/authorize"
    token_url = "https://provider.example.test/oauth/token"

    async def exchange_code(self, *, code: str, redirect_uri: str, client_id: str, client_secret: str) -> dict[str, Any]:
        assert code == "code-1"
        assert redirect_uri == "https://kdcube.example.test/oauth/callback"
        assert client_id == "test-client"
        assert client_secret == "test-secret"
        return {
            "access_token": "token-1",
            "refresh_token": "refresh-1",
            "scope": "provider.read",
            "expires_in": 3600,
        }

    async def fetch_profile(self, *, access_token: str, token: dict[str, Any] | None = None) -> dict[str, Any]:
        assert access_token == "token-1"
        return {
            "external_subject": "external-user-1",
            "email": "user@example.test",
            "display_name": "User Example",
        }

    async def normalize_profile(self, credential: dict[str, Any]) -> dict[str, Any]:
        return {"external_subject": "fallback-user"}


def _oauth_sample_config():
    register_adapter(_FakeOAuthAdapter())
    return user_integrations_config(
        {
            "enabled": True,
            "providers": {
                "test": {
                    "label": "Test Provider",
                    "adapter": "test.oauth",
                    "capabilities": {
                        "test:read": {
                            "label": "Read test data",
                            "provider_scopes": ["provider.read"],
                        }
                    },
                    "connector_apps": {
                        "default": {
                            "label": "Default OAuth app",
                            "client_id": "test-client",
                            "client_secret_ref": "user_integrations.providers.test.connector_apps.default.client_secret",
                            "capability_ceiling": ["test:read"],
                        }
                    },
                }
            },
        }
    )


def _install_fake_storage(monkeypatch):
    props: dict[tuple[str, str, str], Any] = {}
    secrets: dict[tuple[str, str, str], str] = {}

    def get_user_prop(key: str, *, user_id: str | None = None, bundle_id: str | None = None, default: Any = None):
        return props.get((user_id or "", bundle_id or "", key), default)

    def set_user_prop(key: str, value: Any, *, user_id: str | None = None, bundle_id: str | None = None):
        props[(user_id or "", bundle_id or "", key)] = value

    def delete_user_prop(key: str, *, user_id: str | None = None, bundle_id: str | None = None):
        props.pop((user_id or "", bundle_id or "", key), None)

    async def set_user_secret(
        key: str,
        value: str,
        *,
        user_id: str | None = None,
        bundle_id: str | None = None,
    ):
        secrets[(user_id or "", bundle_id or "", key)] = value

    async def get_secret(key: str, *, user_id: str | None = None, bundle_id: str | None = None):
        normalized = key[2:] if key.startswith("u:") else key
        return secrets.get((user_id or "", bundle_id or "", normalized))

    async def delete_user_secret(key: str, *, user_id: str | None = None, bundle_id: str | None = None):
        secrets.pop((user_id or "", bundle_id or "", key), None)

    monkeypatch.setattr(ui_store.sdk_config, "get_user_prop", get_user_prop)
    monkeypatch.setattr(ui_store.sdk_config, "set_user_prop", set_user_prop)
    monkeypatch.setattr(ui_store.sdk_config, "delete_user_prop", delete_user_prop)
    monkeypatch.setattr(ui_store.sdk_config, "set_user_secret", set_user_secret)
    monkeypatch.setattr(ui_store.sdk_config, "get_secret", get_secret)
    monkeypatch.setattr(ui_store.sdk_config, "delete_user_secret", delete_user_secret)
    return props, secrets


def test_config_parses_provider_capabilities_and_connector_apps():
    config = _sample_config()

    provider = config.provider("google")
    assert config.enabled is True
    assert provider is not None
    assert provider.adapter == "google.oauth"
    assert provider.capabilities["gmail:read"].provider_scopes == (
        "https://www.googleapis.com/auth/gmail.readonly",
    )
    assert provider.connector_apps["gmail"].client_id == "client-id"
    assert provider.connector_apps["gmail"].capability_ceiling == ("gmail:read", "gmail:send")
    public = config.to_dict(include_client_ids=True)
    assert public["providers"]["google"]["connector_apps"]["gmail"]["client_id"] == "client-id"
    assert "client_secret_ref" not in public["providers"]["google"]["connector_apps"]["gmail"]


def test_connections_lazy_surface_exposes_user_integrations():
    assert connections.UserIntegrationsClient.__name__ == "UserIntegrationsClient"
    assert connections.UserIntegrationStore.__name__ == "UserIntegrationStore"
    assert connections.UserIntegrationsOperations.__name__ == "UserIntegrationsOperations"


@pytest.mark.asyncio
async def test_store_persists_metadata_in_user_props_and_credentials_in_user_secrets(monkeypatch):
    props, secrets = _install_fake_storage(monkeypatch)
    store = UserIntegrationStore(user_id="user-1")

    stored = await store.upsert_account(
        ConnectedAccount(
            account_id="",
            provider_id="google",
            connector_app_id="gmail",
            external_subject="google-sub-1",
            email="user@example.test",
            display_name="User Example",
            capabilities=("gmail:read",),
        )
    )
    await store.set_credential(stored.credential_id, {"access_token": "token-1", "refresh_token": "refresh-1"})

    accounts = await store.list_accounts(provider_id="google")
    credential = await store.get_credential(stored.credential_id)

    assert len(accounts) == 1
    assert accounts[0].public_dict()["has_credential"] is True
    assert "credential_id" not in accounts[0].public_dict()
    assert credential["access_token"] == "token-1"
    assert any(key[-1].startswith("user_integrations.accounts.") for key in props)
    assert any(key[-1].startswith("user_integrations.credentials.") for key in secrets)

    assert await store.disconnect_account(stored.account_id) is True
    assert await store.list_accounts() == []
    assert await store.get_credential(stored.credential_id) == {}


@pytest.mark.asyncio
async def test_broker_returns_credential_when_capability_and_credential_exist(monkeypatch):
    _install_fake_storage(monkeypatch)
    config = _sample_config()
    store = UserIntegrationStore(user_id="user-1")
    credential_id = credential_id_for("acct-1")
    await store.upsert_account(
        ConnectedAccount(
            account_id="acct-1",
            provider_id="google",
            connector_app_id="gmail",
            external_subject="google-sub-1",
            capabilities=("gmail:read",),
            credential_id=credential_id,
        )
    )
    await store.set_credential(credential_id, {"access_token": "token-1"})

    result = await UserIntegrationBroker(config=config, store=store).ensure_capability(
        provider_id="google",
        capability="gmail:read",
    )

    assert result.ok is True
    assert result.credential is not None
    assert result.credential.credential["access_token"] == "token-1"
    assert result.to_dict()["credential"]["has_credential"] is True
    assert "credential" not in result.to_dict()["credential"]
    assert result.to_dict(include_credential=True)["credential"]["credential"]["access_token"] == "token-1"


@pytest.mark.asyncio
async def test_broker_requires_consent_when_account_missing(monkeypatch):
    _install_fake_storage(monkeypatch)
    config = _sample_config()
    store = UserIntegrationStore(user_id="user-1")

    result = await UserIntegrationBroker(config=config, store=store).ensure_capability(
        provider_id="google",
        capability="gmail:read",
    )

    assert result.ok is False
    assert result.consent_required is True
    assert result.error == "consent_required"


@pytest.mark.asyncio
async def test_broker_requires_account_id_when_multiple_accounts_can_satisfy_capability(monkeypatch):
    _install_fake_storage(monkeypatch)
    config = _sample_config()
    store = UserIntegrationStore(user_id="user-1")
    for account_id in ("acct-1", "acct-2"):
        credential_id = credential_id_for(account_id)
        await store.upsert_account(
            ConnectedAccount(
                account_id=account_id,
                provider_id="google",
                connector_app_id="gmail",
                external_subject=f"sub-{account_id}",
                capabilities=("gmail:read",),
                credential_id=credential_id,
            )
        )
        await store.set_credential(credential_id, {"access_token": f"token-{account_id}"})

    ambiguous = await UserIntegrationBroker(config=config, store=store).ensure_capability(
        provider_id="google",
        capability="gmail:read",
    )
    selected = await UserIntegrationBroker(config=config, store=store).ensure_capability(
        provider_id="google",
        capability="gmail:read",
        account_id="acct-2",
    )

    assert ambiguous.ok is False
    assert ambiguous.error == "account_required"
    assert ambiguous.candidates == ("acct-1", "acct-2")
    assert selected.ok is True
    assert selected.account_id == "acct-2"


@pytest.mark.asyncio
async def test_builtin_adapters_register_and_normalize_profiles():
    import kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.providers  # noqa: F401

    google = resolve_adapter("google.oauth")
    normalized = await google.normalize_profile({"sub": "s-1", "email": "a@example.test", "name": "A User"})
    scopes = google.provider_scopes_for_capabilities(
        ["gmail:read"],
        _sample_config().provider("google").capabilities,
    )

    assert normalized == {
        "external_subject": "s-1",
        "email": "a@example.test",
        "display_name": "A User",
    }
    assert scopes == ["https://www.googleapis.com/auth/gmail.readonly"]


@pytest.mark.asyncio
async def test_operations_connect_credential_catalog_and_disconnect(monkeypatch):
    _install_fake_storage(monkeypatch)
    ops = operations_for_user(user_id="user-1", config=_sample_config())

    connected = await ops.connect_credential(
        {
            "provider": "google",
            "app_id": "gmail",
            "external_subject": "google-sub-1",
            "email": "user@example.test",
            "display_name": "User Example",
            "capabilities": ["gmail:read"],
            "credential": {"access_token": "token-1", "refresh_token": "refresh-1"},
        }
    )
    account_id = connected["account"]["account_id"]
    catalog = await ops.catalog(provider_id="google")
    resolved = await ops.resolve(provider_id="google", capability="gmail:read", account_id=account_id)
    disconnected = await ops.disconnect(account_id=account_id)

    assert connected["ok"] is True
    assert connected["account"]["has_credential"] is True
    assert "credential_id" not in connected["account"]
    assert catalog["accounts"][0]["email"] == "user@example.test"
    assert resolved["ok"] is True
    assert resolved["credential"]["has_credential"] is True
    assert "credential" not in resolved["credential"]
    assert disconnected == {"ok": True, "removed": True, "account_id": account_id}


@pytest.mark.asyncio
async def test_operations_reject_unknown_capability(monkeypatch):
    _install_fake_storage(monkeypatch)
    ops = operations_for_user(user_id="user-1", config=_sample_config())

    with pytest.raises(ValueError, match="unknown provider capability"):
        await ops.connect_credential(
            {
                "provider": "google",
                "app_id": "gmail",
                "external_subject": "google-sub-1",
                "capabilities": ["gmail:delete"],
                "credential": {"access_token": "token-1"},
            }
        )


@pytest.mark.asyncio
async def test_operations_start_and_complete_oauth_stores_user_credential(monkeypatch):
    _install_fake_storage(monkeypatch)
    ops = operations_for_user(user_id="user-1", config=_oauth_sample_config())
    state_store = MemoryOAuthStateStore()

    started = await ops.start_oauth(
        {
            "provider": "test",
            "app_id": "default",
            "capabilities": ["test:read"],
        },
        user_id="user-1",
        callback_url="https://kdcube.example.test/oauth/callback",
        state_store=state_store,
        state_secret="state-secret",
    )

    assert started["ok"] is True
    assert started["redirect_uri"] == "https://kdcube.example.test/oauth/callback"
    assert "client_id=test-client" in started["authorize_url"]
    assert "scope=provider.read" in started["authorize_url"]

    completed = await ops.complete_oauth(
        code="code-1",
        state=started["authorize_url"].split("state=", 1)[1].split("&", 1)[0],
        callback_url="https://kdcube.example.test/oauth/callback",
        state_store=state_store,
        state_secret="state-secret",
        client_secret_resolver=lambda **kwargs: "test-secret",
    )
    catalog = await ops.catalog(provider_id="test")
    resolved = await ops.resolve(
        provider_id="test",
        capability="test:read",
        account_id=completed["account"]["account_id"],
    )

    assert completed["ok"] is True
    assert completed["account"]["email"] == "user@example.test"
    assert catalog["accounts"][0]["has_credential"] is True
    assert resolved["ok"] is True
    assert resolved["credential"]["has_credential"] is True
    assert "credential" not in resolved["credential"]

    with pytest.raises(ValueError, match="already used"):
        await ops.complete_oauth(
            code="code-1",
            state=started["authorize_url"].split("state=", 1)[1].split("&", 1)[0],
            callback_url="https://kdcube.example.test/oauth/callback",
            state_store=state_store,
            state_secret="state-secret",
            client_secret_resolver=lambda **kwargs: "test-secret",
        )
