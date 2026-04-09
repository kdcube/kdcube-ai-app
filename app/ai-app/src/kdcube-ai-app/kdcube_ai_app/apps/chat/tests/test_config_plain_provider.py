from pathlib import Path

import yaml

from kdcube_ai_app.apps.chat.sdk import config as sdk_config


class _NoopSecretsManager:
    def get_secret(self, key: str):
        return None


def test_get_plain_reads_assembly_by_default(monkeypatch, tmp_path):
    for key in (
        "KDCUBE_STORAGE_PATH",
        "CB_BUNDLE_STORAGE_URL",
        "REACT_WORKSPACE_IMPLEMENTATION",
        "REACT_WORKSPACE_GIT_REPO",
        "CLAUDE_CODE_SESSION_STORE_IMPLEMENTATION",
        "CLAUDE_CODE_SESSION_GIT_REPO",
    ):
        monkeypatch.delenv(key, raising=False)
    assembly_path = tmp_path / "assembly.yaml"
    assembly_path.write_text(
        yaml.safe_dump(
            {
                "storage": {
                    "kdcube": "s3://example/kdcube",
                    "bundles": "s3://example/bundles",
                    "workspace": {"type": "git", "repo": "https://example.com/workspace.git"},
                    "claude_code_session": {"type": "git", "repo": "https://example.com/sessions.git"},
                },
                "frontend": {"routes_prefix": "/cisoteria"},
            },
            sort_keys=False,
        )
    )

    monkeypatch.setattr(sdk_config, "get_secrets_manager", lambda _settings: _NoopSecretsManager())
    monkeypatch.setattr(sdk_config, "_ASSEMBLY_YAML_PATH", Path(assembly_path))
    settings = sdk_config.Settings()
    monkeypatch.setattr(sdk_config, "get_settings", lambda: settings)

    assert sdk_config.get_plain("storage.workspace.type") == "git"
    assert sdk_config.read_plain("a:frontend.routes_prefix") == "/cisoteria"
    assert settings.STORAGE_PATH == "s3://example/kdcube"
    assert settings.BUNDLE_STORAGE_URL == "s3://example/bundles"
    assert settings.REACT_WORKSPACE_IMPLEMENTATION == "git"
    assert settings.plain("storage.workspace.repo") == "https://example.com/workspace.git"
    assert settings.REACT_WORKSPACE_GIT_REPO == "https://example.com/workspace.git"
    assert settings.CLAUDE_CODE_SESSION_STORE_IMPLEMENTATION == "git"
    assert settings.CLAUDE_CODE_SESSION_GIT_REPO == "https://example.com/sessions.git"


def test_get_plain_reads_bundles_namespace(monkeypatch, tmp_path):
    bundles_path = tmp_path / "bundles.yaml"
    bundles_path.write_text(
        yaml.safe_dump(
            {
                "default_bundle_id": "demo.bundle@1.0.0",
                "bundles": {
                    "demo.bundle@1.0.0": {
                        "name": "Demo Bundle",
                        "widgets": [{"alias": "chat", "icon": "sparkles"}],
                    }
                },
            },
            sort_keys=False,
        )
    )

    monkeypatch.setattr(sdk_config, "get_secrets_manager", lambda _settings: _NoopSecretsManager())
    monkeypatch.setattr(sdk_config, "_BUNDLES_YAML_PATH", Path(bundles_path))
    settings = sdk_config.Settings()
    monkeypatch.setattr(sdk_config, "get_settings", lambda: settings)

    assert sdk_config.get_plain("b:default_bundle_id") == "demo.bundle@1.0.0"
    assert settings.plain("b:bundles.demo.bundle@1.0.0.name") == "Demo Bundle"
    assert settings.plain("b:bundles.demo.bundle@1.0.0.widgets.0.alias") == "chat"


def test_get_plain_returns_default_when_path_missing(monkeypatch, tmp_path):
    assembly_path = tmp_path / "assembly.yaml"
    assembly_path.write_text(yaml.safe_dump({"storage": {"workspace": {"type": "custom"}}}, sort_keys=False))

    monkeypatch.setattr(sdk_config, "get_secrets_manager", lambda _settings: _NoopSecretsManager())
    monkeypatch.setattr(sdk_config, "_ASSEMBLY_YAML_PATH", Path(assembly_path))
    settings = sdk_config.Settings()
    monkeypatch.setattr(sdk_config, "get_settings", lambda: settings)

    assert sdk_config.get_plain("storage.workspace.repo", default="none") == "none"
