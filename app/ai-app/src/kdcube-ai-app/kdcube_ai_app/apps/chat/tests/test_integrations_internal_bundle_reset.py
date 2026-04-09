from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kdcube_ai_app.apps.chat.proc.rest.integrations import mount_integrations_routers
from kdcube_ai_app.apps.chat.proc.rest.integrations import integrations


class _Entry:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return dict(self._payload)


class _Registry:
    def __init__(self, *, default_bundle_id: str, bundles: dict[str, _Entry]):
        self.default_bundle_id = default_bundle_id
        self.bundles = bundles


def test_internal_reset_env_reapplies_registry(monkeypatch):
    app = FastAPI()
    app.state.redis_async = object()
    mount_integrations_routers(app)

    calls: dict[str, object] = {}

    async def fake_reset_registry_from_env(redis, tenant, project):
        calls["reset"] = (redis, tenant, project)
        return _Registry(
            default_bundle_id="demo.bundle@1.0.0",
            bundles={
                "demo.bundle@1.0.0": _Entry(
                    {
                        "id": "demo.bundle@1.0.0",
                        "path": "/bundles/demo",
                        "module": "demo.entrypoint",
                    }
                )
            },
        )

    async def fake_set_registry_async(registry, default_bundle_id):
        calls["set_registry"] = (registry, default_bundle_id)

    def fake_serialize_to_env(registry, default_bundle_id):
        calls["serialize"] = (registry, default_bundle_id)
        return "ok"

    def fake_clear_agentic_caches():
        calls["cleared"] = True

    class _Redis:
        async def publish(self, channel, payload):
            calls["publish"] = (channel, payload)
            return 1

    app.state.redis_async = _Redis()

    monkeypatch.setattr(integrations, "get_settings", lambda: SimpleNamespace(TENANT="example-product", PROJECT="chatbot"))
    monkeypatch.setattr(integrations, "_LOCALHOST", {"testclient", "127.0.0.1", "::1"})

    import kdcube_ai_app.infra.plugin.bundle_store as bundle_store
    import kdcube_ai_app.infra.plugin.bundle_registry as bundle_registry
    import kdcube_ai_app.infra.plugin.agentic_loader as agentic_loader

    monkeypatch.setattr(bundle_store, "reset_registry_from_env", fake_reset_registry_from_env)
    monkeypatch.setattr(bundle_registry, "set_registry_async", fake_set_registry_async)
    monkeypatch.setattr(bundle_registry, "serialize_to_env", fake_serialize_to_env)
    monkeypatch.setattr(agentic_loader, "clear_agentic_caches", fake_clear_agentic_caches)

    client = TestClient(app)
    response = client.post("/internal/bundles/reset-env", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["source"] == "env"
    assert calls["reset"][1:] == ("example-product", "chatbot")
    assert calls["set_registry"][1] == "demo.bundle@1.0.0"
    assert calls["serialize"][1] == "demo.bundle@1.0.0"
    assert calls["cleared"] is True
    assert calls["publish"][0] == "kdcube:config:bundles:update:example-product:chatbot"
