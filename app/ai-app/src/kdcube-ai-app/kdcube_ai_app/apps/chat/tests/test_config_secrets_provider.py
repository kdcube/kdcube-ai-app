from types import SimpleNamespace

import pytest

from kdcube_ai_app.apps.chat.sdk import config as sdk_config
from kdcube_ai_app.apps.chat.sdk.protocol import ChatTaskActor, ChatTaskPayload, ChatTaskRouting, ChatTaskUser
from kdcube_ai_app.apps.chat.sdk.runtime import comm_ctx


class _FakeSecretsManager:
    def __init__(self):
        self.set_calls = []

    def get_secret(self, key: str):
        values = {
            "services.openai.api_key": "sk-openai-test",
            "services.anthropic.api_key": "sk-anthropic-test",
            "services.git.http_token": "gh-token-test",
            "infra.postgres.password": "pg-secret-test",
            "infra.redis.password": "redis-secret-test",
            "bundles.bundle.demo.secrets.user_management.cognito_user_pool_id": "pool-123",
        }
        return values.get(key)

    def get_user_secret(self, *, user_id: str, key: str, bundle_id: str | None = None):
        values = {
            ("user-1", "bundle.demo", "anthropic.api_key"): "sk-user-anthropic",
        }
        return values.get((user_id, bundle_id, key))

    def set_secret(self, key: str, value: str):
        self.set_calls.append((key, value))


class _FakePropsManager:
    def get_user_prop(self, *, user_id: str, key: str, bundle_id: str | None = None):
        values = {
            ("user-1", "bundle.demo", "preferences.theme"): "dark",
        }
        return values.get((user_id, bundle_id, key))

    def list_user_props(self, *, user_id: str, bundle_id: str | None = None):
        values = {
            ("user-1", "bundle.demo"): {"preferences.theme": "dark"},
        }
        return values.get((user_id, bundle_id), {})


def test_settings_reads_secrets_through_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("GIT_HTTP_TOKEN", raising=False)
    monkeypatch.delenv("GIT_HTTP_USER", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(sdk_config, "get_secrets_manager", lambda _settings: _FakeSecretsManager())

    settings = sdk_config.Settings()

    assert settings.OPENAI_API_KEY == "sk-openai-test"
    assert settings.ANTHROPIC_API_KEY == "sk-anthropic-test"
    assert settings.secret("services.openai.api_key") == "sk-openai-test"
    assert settings.GIT_HTTP_TOKEN == "gh-token-test"
    assert settings.GIT_HTTP_USER == "x-access-token"


def test_settings_reads_infra_passwords_through_provider_when_env_absent(monkeypatch):
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    monkeypatch.setattr(sdk_config, "get_secrets_manager", lambda _settings: _FakeSecretsManager())

    settings = sdk_config.Settings()

    assert settings.PGPASSWORD == "pg-secret-test"
    assert settings.REDIS_PASSWORD == "redis-secret-test"


def test_get_user_secret_uses_request_context_scope(monkeypatch):
    monkeypatch.setattr(sdk_config, "get_secrets_manager", lambda _settings: _FakeSecretsManager())
    monkeypatch.setattr(
        comm_ctx,
        "get_current_request_context",
        lambda: ChatTaskPayload(
            routing=ChatTaskRouting(bundle_id="bundle.demo", session_id="s-1"),
            user=ChatTaskUser(user_type="registered", user_id="user-1"),
        ),
    )

    assert sdk_config.get_user_secret("anthropic.api_key") == "sk-user-anthropic"


def test_get_user_prop_uses_request_context_scope(monkeypatch):
    monkeypatch.setattr(sdk_config, "get_props_manager", lambda: _FakePropsManager())
    monkeypatch.setattr(
        comm_ctx,
        "get_current_request_context",
        lambda: ChatTaskPayload(
            routing=ChatTaskRouting(bundle_id="bundle.demo", session_id="s-1"),
            user=ChatTaskUser(user_type="registered", user_id="user-1"),
        ),
    )

    assert sdk_config.get_user_prop("preferences.theme") == "dark"
    assert sdk_config.get_user_props() == {"preferences.theme": "dark"}


def test_get_secret_bundle_namespace_uses_request_context_scope(monkeypatch):
    monkeypatch.setattr(sdk_config, "get_secrets_manager", lambda _settings: _FakeSecretsManager())
    monkeypatch.setattr(
        comm_ctx,
        "get_current_request_context",
        lambda: ChatTaskPayload(
            routing=ChatTaskRouting(bundle_id="bundle.demo", session_id="s-1"),
            user=ChatTaskUser(user_type="registered", user_id="user-1"),
        ),
    )

    assert sdk_config.get_secret("b:user_management.cognito_user_pool_id") == "pool-123"


def test_get_secret_bundle_namespace_uses_explicit_bundle_contextvar(monkeypatch):
    monkeypatch.setattr(sdk_config, "get_secrets_manager", lambda _settings: _FakeSecretsManager())
    monkeypatch.setattr(comm_ctx, "get_current_request_context", lambda: None)

    with comm_ctx.bind_current_bundle_id("bundle.demo"):
        assert sdk_config.get_secret("b:user_management.cognito_user_pool_id") == "pool-123"


def test_get_secret_bundle_namespace_uses_bundle_env_fallback(monkeypatch):
    monkeypatch.setattr(sdk_config, "get_secrets_manager", lambda _settings: _FakeSecretsManager())
    monkeypatch.setattr(comm_ctx, "get_current_request_context", lambda: None)
    monkeypatch.setenv("KDCUBE_BUNDLE_ID", "bundle.demo")

    assert sdk_config.get_secret("b:user_management.cognito_user_pool_id") == "pool-123"


@pytest.mark.asyncio
async def test_set_bundle_secret_uses_request_context_bundle_scope(monkeypatch):
    manager = _FakeSecretsManager()
    monkeypatch.setattr(sdk_config, "get_secrets_manager", lambda _settings: manager)
    monkeypatch.setattr(
        sdk_config,
        "get_settings",
        lambda: SimpleNamespace(TENANT="demo-tenant", PROJECT="demo-project"),
    )
    monkeypatch.setattr(
        comm_ctx,
        "get_current_request_context",
        lambda: ChatTaskPayload(
            routing=ChatTaskRouting(bundle_id="bundle.demo", session_id="s-1"),
            actor=ChatTaskActor(tenant_id="ctx-tenant", project_id="ctx-project"),
            user=ChatTaskUser(user_type="registered", user_id="user-1"),
        ),
    )

    await sdk_config.set_bundle_secret("api.token", "secret-value")

    assert manager.set_calls == [
        ("bundles.bundle.demo.secrets.api.token", "secret-value"),
    ]


@pytest.mark.asyncio
async def test_set_bundle_prop_uses_request_context_scope_and_merges_nested_key(monkeypatch):
    calls = {}

    async def _fake_patch_bundle_props(redis, *, tenant, project, bundle_id, props_patch, actor=None, source=None):
        calls["patch"] = {
            "redis": redis,
            "tenant": tenant,
            "project": project,
            "bundle_id": bundle_id,
            "props_patch": props_patch,
            "actor": actor,
            "source": source,
        }

    redis_client = object()
    monkeypatch.setattr(
        sdk_config,
        "get_settings",
        lambda: SimpleNamespace(
            REDIS_URL="redis://test",
            TENANT="settings-tenant",
            PROJECT="settings-project",
        ),
    )
    monkeypatch.setattr(
        comm_ctx,
        "get_current_request_context",
        lambda: ChatTaskPayload(
            routing=ChatTaskRouting(bundle_id="bundle.demo", session_id="s-1"),
            actor=ChatTaskActor(tenant_id="ctx-tenant", project_id="ctx-project"),
            user=ChatTaskUser(user_type="registered", user_id="user-1"),
        ),
    )

    import kdcube_ai_app.infra.redis.client as redis_client_mod
    import kdcube_ai_app.infra.plugin.bundle_store as bundle_store_mod

    monkeypatch.setattr(redis_client_mod, "get_async_redis_client", lambda url: redis_client)
    monkeypatch.setattr(bundle_store_mod, "patch_bundle_props", _fake_patch_bundle_props)

    await sdk_config.set_bundle_prop("features.sync.enabled", False)

    assert calls["patch"] == {
        "redis": redis_client,
        "tenant": "ctx-tenant",
        "project": "ctx-project",
        "bundle_id": "bundle.demo",
        "props_patch": {
            "features": {
                "sync": {"enabled": False},
            }
        },
        "actor": None,
        "source": None,
    }


@pytest.mark.asyncio
async def test_set_bundle_props_merges_patch_and_publishes_once(monkeypatch):
    calls = {}

    async def _fake_patch_bundle_props(redis, *, tenant, project, bundle_id, props_patch, actor=None, source=None):
        calls["patch"] = {
            "redis": redis,
            "tenant": tenant,
            "project": project,
            "bundle_id": bundle_id,
            "props_patch": props_patch,
            "actor": actor,
            "source": source,
        }

    redis_client = object()
    monkeypatch.setattr(
        sdk_config,
        "get_settings",
        lambda: SimpleNamespace(
            REDIS_URL="redis://test",
            TENANT="settings-tenant",
            PROJECT="settings-project",
        ),
    )
    monkeypatch.setattr(
        comm_ctx,
        "get_current_request_context",
        lambda: ChatTaskPayload(
            routing=ChatTaskRouting(bundle_id="bundle.demo", session_id="s-1"),
            actor=ChatTaskActor(tenant_id="ctx-tenant", project_id="ctx-project"),
            user=ChatTaskUser(user_type="registered", user_id="user-1"),
        ),
    )

    import kdcube_ai_app.infra.redis.client as redis_client_mod
    import kdcube_ai_app.infra.plugin.bundle_store as bundle_store_mod

    monkeypatch.setattr(redis_client_mod, "get_async_redis_client", lambda url: redis_client)
    monkeypatch.setattr(bundle_store_mod, "patch_bundle_props", _fake_patch_bundle_props)

    await sdk_config.set_bundle_props(
        {
            "subsystems": {
                "news": {
                    "pipeline": {
                        "cron": "57 19 * * *",
                        "first_run_days": 3,
                    }
                }
            }
        }
    )

    assert calls["patch"] == {
        "redis": redis_client,
        "tenant": "ctx-tenant",
        "project": "ctx-project",
        "bundle_id": "bundle.demo",
        "props_patch": {
            "subsystems": {
                "news": {
                    "pipeline": {
                        "cron": "57 19 * * *",
                        "first_run_days": 3,
                    }
                }
            }
        },
        "actor": None,
        "source": None,
    }
