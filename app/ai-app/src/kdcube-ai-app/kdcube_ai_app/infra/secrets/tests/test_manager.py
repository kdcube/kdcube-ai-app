import json
from types import SimpleNamespace

import pytest

from kdcube_ai_app.infra.secrets import (
    AwsSecretsManagerSecretsManager,
    SecretsManagerConfig,
    SecretsFileSecretsManager,
    build_secrets_manager_config,
    get_secrets_manager,
    reset_secrets_manager_cache,
)


class _FakeAwsClientError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class _FakeAwsSecretsClient:
    def __init__(self, initial: dict[str, str] | None = None):
        self.data = dict(initial or {})

    def get_secret_value(self, *, SecretId: str):
        if SecretId not in self.data:
            raise _FakeAwsClientError("ResourceNotFoundException")
        return {"SecretString": self.data[SecretId]}

    def put_secret_value(self, *, SecretId: str, SecretString: str):
        if SecretId not in self.data:
            raise _FakeAwsClientError("ResourceNotFoundException")
        self.data[SecretId] = SecretString
        return {"ARN": SecretId}

    def create_secret(self, *, Name: str, SecretString: str):
        self.data[Name] = SecretString
        return {"ARN": Name}

    def delete_secret(self, *, SecretId: str, ForceDeleteWithoutRecovery: bool):
        if SecretId not in self.data:
            raise _FakeAwsClientError("ResourceNotFoundException")
        self.data.pop(SecretId, None)
        return {"ARN": SecretId}


def test_build_secrets_manager_config_uses_env_and_ignores_gateway_json(monkeypatch):
    monkeypatch.setenv("GATEWAY_CONFIG_JSON", '{"secrets":{"provider":"in-memory"}}')
    monkeypatch.setenv("GATEWAY_COMPONENT", "proc")
    monkeypatch.setenv("SECRETS_PROVIDER", "local")
    monkeypatch.setenv("SECRETS_URL", "http://kdcube-secrets:7777")
    monkeypatch.setenv("SECRETS_TOKEN", "proc-read")
    monkeypatch.setenv("SECRETS_ADMIN_TOKEN", "proc-admin")
    reset_secrets_manager_cache()

    config = build_secrets_manager_config()

    assert config.provider == "secrets-service"
    assert config.component == "proc"
    assert config.url == "http://kdcube-secrets:7777"
    assert config.token == "proc-read"
    assert config.admin_token == "proc-admin"


def test_aws_sm_secret_path_uses_grouped_documents():
    manager = AwsSecretsManagerSecretsManager(
        SecretsManagerConfig(
            provider="aws-sm",
            component="proc",
            aws_sm_prefix="kdcube/demo/demo-march",
        )
    )

    assert manager._secret_id("services.openai.api_key") == "kdcube/demo/demo-march/platform/secrets"
    assert (
        manager._secret_id("bundles.react@2026-03-15.secrets.openai.api_key")
        == "kdcube/demo/demo-march/bundles/react@2026-03-15/secrets"
    )
    assert (
        manager._secret_id("users.user-1.bundles.rms@06-04-26-156.secrets.anthropic.api_key")
        == "kdcube/demo/demo-march/users/user-1/bundles/rms@06-04-26-156/secrets"
    )
    assert manager._legacy_secret_id("services.openai.api_key") == "kdcube/demo/demo-march/services/openai/api_key"
    assert (
        manager._legacy_secret_id("bundles.react@2026-03-15.secrets.openai.api_key")
        == "kdcube/demo/demo-march/bundles/react@2026-03-15/secrets/openai/api_key"
    )


def test_aws_sm_manager_reads_grouped_documents_and_virtual_metadata():
    manager = AwsSecretsManagerSecretsManager(
        SecretsManagerConfig(provider="aws-sm", component="proc", aws_sm_prefix="kdcube/demo/demo-march")
    )
    manager._client = _FakeAwsSecretsClient(
        {
            "kdcube/demo/demo-march/platform/secrets": json.dumps(
                {"services": {"openai": {"api_key": "sk-openai"}}}
            ),
            "kdcube/demo/demo-march/bundles/user-mgmt@1-0/secrets": json.dumps(
                {"user_management": {"cognito_user_pool_id": "pool-123", "dry_run": "false"}}
            ),
            "kdcube/demo/demo-march/users/user-1/bundles/user-mgmt@1-0/secrets": json.dumps(
                {"google": {"refresh_token": "rt-user"}}
            ),
        }
    )

    assert manager.get_secret("services.openai.api_key") == "sk-openai"
    assert (
        manager.get_secret("bundles.user-mgmt@1-0.secrets.user_management.cognito_user_pool_id") == "pool-123"
    )
    assert (
        manager.get_secret("users.user-1.bundles.user-mgmt@1-0.secrets.google.refresh_token") == "rt-user"
    )
    assert json.loads(manager.get_secret("bundles.user-mgmt@1-0.secrets.__keys") or "[]") == [
        "bundles.user-mgmt@1-0.secrets.user_management.cognito_user_pool_id",
        "bundles.user-mgmt@1-0.secrets.user_management.dry_run",
    ]


def test_aws_sm_manager_falls_back_to_aggregate_bundle_blob_and_legacy_leafs():
    manager = AwsSecretsManagerSecretsManager(
        SecretsManagerConfig(provider="aws-sm", component="proc", aws_sm_prefix="kdcube/demo/demo-march")
    )
    manager._client = _FakeAwsSecretsClient(
        {
            "kdcube/demo/demo-march/bundles/secrets": json.dumps(
                {
                    "user-mgmt@1-0": {
                        "user_management": {
                            "cognito_user_pool_id": "pool-from-blob",
                            "sheets_key": "sheet-from-blob",
                        }
                    }
                }
            ),
            "kdcube/demo/demo-march/services/openai/api_key": "sk-legacy-openai",
        }
    )

    assert (
        manager.get_secret("bundles.user-mgmt@1-0.secrets.user_management.cognito_user_pool_id")
        == "pool-from-blob"
    )
    assert (
        manager.get_secret("bundles.user-mgmt@1-0.secrets.user_management.sheets_key")
        == "sheet-from-blob"
    )
    assert manager.get_secret("services.openai.api_key") == "sk-legacy-openai"


def test_aws_sm_manager_writes_and_deletes_grouped_bundle_documents():
    manager = AwsSecretsManagerSecretsManager(
        SecretsManagerConfig(provider="aws-sm", component="proc", aws_sm_prefix="kdcube/demo/demo-march")
    )
    client = _FakeAwsSecretsClient()
    manager._client = client

    manager.set_secret("bundles.user-mgmt@1-0.secrets.user_management.cognito_user_pool_id", "pool-123")
    manager.set_secret("bundles.user-mgmt@1-0.secrets.user_management.sheets_key", "sheet-1")
    manager.set_secret("bundles.user-mgmt@1-0.secrets.__keys", json.dumps(["ignored"]))

    stored = json.loads(client.data["kdcube/demo/demo-march/bundles/user-mgmt@1-0/secrets"])
    assert stored == {
        "user_management": {
            "cognito_user_pool_id": "pool-123",
            "sheets_key": "sheet-1",
        }
    }

    manager.delete_secret("bundles.user-mgmt@1-0.secrets.user_management.sheets_key")
    stored = json.loads(client.data["kdcube/demo/demo-march/bundles/user-mgmt@1-0/secrets"])
    assert stored == {"user_management": {"cognito_user_pool_id": "pool-123"}}

    manager.delete_secret("bundles.user-mgmt@1-0.secrets.user_management.cognito_user_pool_id")
    assert "kdcube/demo/demo-march/bundles/user-mgmt@1-0/secrets" not in client.data


def test_aws_sm_manager_cross_replica_writes_use_distributed_doc_lock(monkeypatch):
    from kdcube_ai_app.infra import namespaces
    from kdcube_ai_app.infra.redis import client as redis_client

    fake_redis = _FakeSyncRedis()
    shared_client = _FakeAwsSecretsClient()
    monkeypatch.setattr(redis_client, "get_sync_redis_client", lambda *args, **kwargs: fake_redis)

    cfg = SecretsManagerConfig(
        provider="aws-sm",
        component="proc",
        tenant="demo",
        project="demo-project",
        redis_url="redis://fake",
        aws_sm_prefix="kdcube/demo/demo-project",
    )
    manager_a = AwsSecretsManagerSecretsManager(cfg)
    manager_b = AwsSecretsManagerSecretsManager(cfg)
    manager_a._client = shared_client
    manager_b._client = shared_client

    secret_id = "kdcube/demo/demo-project/bundles/user-mgmt@1-0/secrets"
    lock_key = namespaces.CONFIG.BUNDLES.SECRETS_AWS_SM_LOCK_FMT.format(
        tenant="demo",
        project="demo-project",
        doc=secret_id.replace("/", ":"),
    )

    manager_a.set_many(
        {
            "bundles.user-mgmt@1-0.secrets.user_management.cognito_user_pool_id": "pool-123",
            "bundles.user-mgmt@1-0.secrets.user_management.sheets_key": "sheet-1",
        }
    )

    assert lock_key not in fake_redis.data
    assert (
        manager_b.get_secret("bundles.user-mgmt@1-0.secrets.user_management.cognito_user_pool_id")
        == "pool-123"
    )
    assert manager_b.get_secret("bundles.user-mgmt@1-0.secrets.user_management.sheets_key") == "sheet-1"


def test_build_secrets_manager_config_defaults_prefix_from_tenant_and_project(monkeypatch):
    reset_secrets_manager_cache()

    config = build_secrets_manager_config(
        SimpleNamespace(
            TENANT="demo",
            PROJECT="demo-march",
        )
    )

    assert config.tenant == "demo"
    assert config.project == "demo-march"
    assert config.aws_sm_prefix == "kdcube/demo/demo-march"


def test_build_secrets_manager_config_prefers_explicit_prefix_from_settings():
    reset_secrets_manager_cache()

    config = build_secrets_manager_config(
        SimpleNamespace(
            TENANT="demo",
            PROJECT="demo-march",
            SECRETS_SM_PREFIX="kdcube/custom/prefix",
        )
    )

    assert config.tenant == "demo"
    assert config.project == "demo-march"
    assert config.aws_sm_prefix == "kdcube/custom/prefix"


def test_build_secrets_manager_config_uses_secrets_file_when_yaml_is_configured(monkeypatch):
    reset_secrets_manager_cache()
    monkeypatch.delenv("SECRETS_PROVIDER", raising=False)
    monkeypatch.setenv("GLOBAL_SECRETS_YAML", "file:///tmp/global-secrets.yaml")

    config = build_secrets_manager_config(
        SimpleNamespace(
            TENANT="demo",
            PROJECT="demo-march",
        )
    )

    assert config.provider == "secrets-file"
    assert config.global_secrets_yaml == "file:///tmp/global-secrets.yaml"


def test_secrets_file_manager_reads_global_and_bundle_yaml(tmp_path, monkeypatch):
    global_file = tmp_path / "secrets.yaml"
    bundle_file = tmp_path / "bundles.secrets.yaml"
    global_file.write_text(
        "\n".join(
            [
                "services:",
                "  openai:",
                "    api_key: sk-global",
                "  anthropic:",
                "    claude_code_key: sk-claude-code",
            ]
        ),
        encoding="utf-8",
    )
    bundle_file.write_text(
        "\n".join(
            [
                "bundles:",
                "  version: '1'",
                "  items:",
                "    - id: 'kdcube.copilot@2026-04-03-19-05'",
                "      secrets:",
                "        telegram:",
                "          webhook_secret: tg-secret",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("SECRETS_PROVIDER", "secrets-file")
    monkeypatch.setenv("GLOBAL_SECRETS_YAML", global_file.resolve().as_uri())
    monkeypatch.setenv("BUNDLE_SECRETS_YAML", bundle_file.resolve().as_uri())
    reset_secrets_manager_cache()

    manager = get_secrets_manager(
        SimpleNamespace(
            TENANT="demo",
            PROJECT="demo-march",
            SECRETS_PROVIDER="secrets-file",
            GLOBAL_SECRETS_YAML=global_file.resolve().as_uri(),
            BUNDLE_SECRETS_YAML=bundle_file.resolve().as_uri(),
        )
    )

    assert manager.get_secret("services.openai.api_key") == "sk-global"
    assert manager.get_secret("services.anthropic.claude_code_key") == "sk-claude-code"
    assert (
        manager.get_secret(
            "bundles.kdcube.copilot@2026-04-03-19-05.secrets.telegram.webhook_secret"
        )
        == "tg-secret"
    )
    assert json.loads(
        manager.get_secret("bundles.kdcube.copilot@2026-04-03-19-05.secrets.__keys") or "[]"
    ) == [
        "bundles.kdcube.copilot@2026-04-03-19-05.secrets.telegram.webhook_secret"
    ]


def test_secrets_file_manager_writes_global_and_bundle_yaml(tmp_path, monkeypatch):
    global_file = tmp_path / "secrets.yaml"
    bundle_file = tmp_path / "bundles.secrets.yaml"

    monkeypatch.setenv("SECRETS_PROVIDER", "secrets-file")
    monkeypatch.setenv("GLOBAL_SECRETS_YAML", global_file.resolve().as_uri())
    monkeypatch.setenv("BUNDLE_SECRETS_YAML", bundle_file.resolve().as_uri())
    reset_secrets_manager_cache()

    manager = get_secrets_manager(
        SimpleNamespace(
            TENANT="demo",
            PROJECT="demo-march",
            SECRETS_PROVIDER="secrets-file",
            GLOBAL_SECRETS_YAML=global_file.resolve().as_uri(),
            BUNDLE_SECRETS_YAML=bundle_file.resolve().as_uri(),
        )
    )

    assert manager.can_write() is True

    manager.set_secret("services.openai.api_key", "sk-new")
    manager.set_many(
        {
            "bundles.kdcube.copilot@2026-04-03-19-05.secrets.telegram.webhook_secret": "tg-secret",
            "bundles.kdcube.copilot@2026-04-03-19-05.secrets.docs.token": "docs-secret",
        }
    )

    assert manager.get_secret("services.openai.api_key") == "sk-new"
    assert (
        manager.get_secret(
            "bundles.kdcube.copilot@2026-04-03-19-05.secrets.telegram.webhook_secret"
        )
        == "tg-secret"
    )
    assert json.loads(
        manager.get_secret("bundles.kdcube.copilot@2026-04-03-19-05.secrets.__keys") or "[]"
    ) == [
        "bundles.kdcube.copilot@2026-04-03-19-05.secrets.docs.token",
        "bundles.kdcube.copilot@2026-04-03-19-05.secrets.telegram.webhook_secret",
    ]

    assert "sk-new" in global_file.read_text(encoding="utf-8")
    bundle_text = bundle_file.read_text(encoding="utf-8")
    assert "kdcube.copilot@2026-04-03-19-05" in bundle_text
    assert "tg-secret" in bundle_text
    assert "docs-secret" in bundle_text

    manager.delete_secret("services.openai.api_key")
    manager.delete_many(
        [
            "bundles.kdcube.copilot@2026-04-03-19-05.secrets.telegram.webhook_secret",
            "bundles.kdcube.copilot@2026-04-03-19-05.secrets.docs.token",
        ]
    )

    assert manager.get_secret("services.openai.api_key") is None
    assert (
        manager.get_secret(
            "bundles.kdcube.copilot@2026-04-03-19-05.secrets.telegram.webhook_secret"
        )
        is None
    )
    assert manager.get_secret("bundles.kdcube.copilot@2026-04-03-19-05.secrets.__keys") is None


def test_secrets_file_manager_reads_and_writes_user_bundle_secrets(tmp_path, monkeypatch):
    global_file = tmp_path / "secrets.yaml"
    monkeypatch.setenv("SECRETS_PROVIDER", "secrets-file")
    monkeypatch.setenv("GLOBAL_SECRETS_YAML", global_file.resolve().as_uri())
    reset_secrets_manager_cache()

    manager = get_secrets_manager(
        SimpleNamespace(
            TENANT="demo",
            PROJECT="demo-march",
            SECRETS_PROVIDER="secrets-file",
            GLOBAL_SECRETS_YAML=global_file.resolve().as_uri(),
        )
    )

    manager.set_user_secret(
        user_id="user-1",
        bundle_id="rms@06-04-26-156",
        key="anthropic.api_key",
        value="sk-user",
    )

    assert (
        manager.get_user_secret(
            user_id="user-1",
            bundle_id="rms@06-04-26-156",
            key="anthropic.api_key",
        )
        == "sk-user"
    )
    text = global_file.read_text(encoding="utf-8")
    assert "users:" in text
    assert "user-1:" in text
    assert "rms@06-04-26-156" in text
    assert "sk-user" in text


class _FakeSyncRedis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    def eval(self, _script, _keys_count, key, token):
        if self.data.get(key) == token:
            self.data.pop(key, None)
            return 1
        return 0


def test_secrets_file_manager_cross_replica_reads_current_yaml(tmp_path, monkeypatch):
    from kdcube_ai_app.infra import namespaces
    from kdcube_ai_app.infra.redis import client as redis_client

    global_file = tmp_path / "secrets.yaml"
    global_file.write_text("services:\n  openai:\n    api_key: sk-old\n", encoding="utf-8")

    fake_redis = _FakeSyncRedis()
    monkeypatch.setattr(redis_client, "get_sync_redis_client", lambda *args, **kwargs: fake_redis)

    cfg = SecretsManagerConfig(
        provider="secrets-file",
        component="proc",
        tenant="demo",
        project="demo-project",
        redis_url="redis://fake",
        global_secrets_yaml=global_file.resolve().as_uri(),
    )

    manager_a = SecretsFileSecretsManager(cfg)
    manager_b = SecretsFileSecretsManager(cfg)

    lock_key = namespaces.CONFIG.BUNDLES.SECRETS_FILE_LOCK_FMT.format(
        tenant="demo",
        project="demo-project",
    )

    assert manager_a.get_secret("services.openai.api_key") == "sk-old"
    assert manager_b.get_secret("services.openai.api_key") == "sk-old"

    manager_a.set_secret("services.openai.api_key", "sk-new")

    assert lock_key not in fake_redis.data
    assert manager_b.get_secret("services.openai.api_key") == "sk-new"
