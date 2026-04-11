from kdcube_ai_app.apps.chat.sdk import config as sdk_config
from kdcube_ai_app.apps.chat.sdk.protocol import ChatTaskPayload, ChatTaskRouting, ChatTaskUser
from kdcube_ai_app.apps.chat.sdk.runtime import comm_ctx


class _FakeSecretsManager:
    def get_secret(self, key: str):
        values = {
            "services.openai.api_key": "sk-openai-test",
            "services.anthropic.api_key": "sk-anthropic-test",
            "services.git.http_token": "gh-token-test",
            "bundles.bundle.demo.secrets.user_management.cognito_user_pool_id": "pool-123",
        }
        return values.get(key)

    def get_user_secret(self, *, user_id: str, key: str, bundle_id: str | None = None):
        values = {
            ("user-1", "bundle.demo", "anthropic.api_key"): "sk-user-anthropic",
        }
        return values.get((user_id, bundle_id, key))


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
