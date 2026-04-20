from types import SimpleNamespace

from kdcube_ai_app.infra.gateway import config as gateway_config


def test_config_from_dict_resolves_placeholder_scope_from_settings(monkeypatch):
    monkeypatch.delenv("TENANT_ID", raising=False)
    monkeypatch.delenv("DEFAULT_PROJECT_NAME", raising=False)
    monkeypatch.delenv("PROJECT_ID", raising=False)
    monkeypatch.setattr(
        gateway_config,
        "get_settings",
        lambda: SimpleNamespace(
            REDIS_URL="redis://example",
            TENANT="demo-tenant",
            PROJECT="demo-project",
        ),
    )

    cfg = gateway_config._config_from_dict(  # noqa: SLF001
        {
            "tenant": "TENANT_ID",
            "project": "PROJECT_ID",
            "profile": "development",
        }
    )

    assert cfg.tenant_id == "demo-tenant"
    assert cfg.project_id == "demo-project"


def test_config_from_dict_keeps_explicit_scope_values(monkeypatch):
    monkeypatch.setattr(
        gateway_config,
        "get_settings",
        lambda: SimpleNamespace(
            REDIS_URL="redis://example",
            TENANT="settings-tenant",
            PROJECT="settings-project",
        ),
    )

    cfg = gateway_config._config_from_dict(  # noqa: SLF001
        {
            "tenant": "tenant-a",
            "project": "project-a",
            "profile": "development",
        }
    )

    assert cfg.tenant_id == "tenant-a"
    assert cfg.project_id == "project-a"
