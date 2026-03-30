from types import SimpleNamespace

import pytest

from kdcube_ai_app.infra.plugin import bundle_registry
from kdcube_ai_app.infra.plugin.bundle_store import BundleEntry, BundlesRegistry


class _FakeRedis:
    pass


@pytest.mark.asyncio
async def test_load_persisted_registry_from_runtime_ctx_prefers_state_redis_async(monkeypatch):
    redis = _FakeRedis()
    runtime_ctx = SimpleNamespace(redis_async=redis)

    async def _load_store_registry(redis_client, tenant, project):
        assert redis_client is redis
        assert tenant == "tenant-a"
        assert project == "project-a"
        return BundlesRegistry(
            default_bundle_id="bundle.demo",
            bundles={
                "bundle.demo": BundleEntry(
                    id="bundle.demo",
                    path="/bundles/bundle.demo",
                    module="entrypoint",
                )
            },
        )

    monkeypatch.setattr(bundle_registry, "_load_store_registry", _load_store_registry, raising=False)

    reg = await bundle_registry.load_persisted_registry_from_runtime_ctx(
        runtime_ctx,
        "tenant-a",
        "project-a",
    )

    assert reg is not None
    assert reg.default_bundle_id == "bundle.demo"


@pytest.mark.asyncio
async def test_resolve_default_bundle_id_from_runtime_ctx_falls_back_to_middleware_redis(monkeypatch):
    redis = _FakeRedis()
    runtime_ctx = SimpleNamespace(middleware=SimpleNamespace(redis=redis))

    async def _load_store_registry(redis_client, tenant, project):
        assert redis_client is redis
        return BundlesRegistry(
            default_bundle_id="bundle.demo",
            bundles={
                "bundle.demo": BundleEntry(
                    id="bundle.demo",
                    path="/bundles/bundle.demo",
                    module="entrypoint",
                )
            },
        )

    monkeypatch.setattr(bundle_registry, "_load_store_registry", _load_store_registry, raising=False)

    resolved = await bundle_registry.resolve_default_bundle_id_from_runtime_ctx(
        runtime_ctx,
        "tenant-a",
        "project-a",
    )

    assert resolved == "bundle.demo"


@pytest.mark.asyncio
async def test_resolve_default_bundle_id_from_runtime_ctx_rejects_missing_default(monkeypatch):
    runtime_ctx = SimpleNamespace(redis_async=_FakeRedis())

    async def _load_store_registry(redis_client, tenant, project):
        del redis_client, tenant, project
        return BundlesRegistry(
            default_bundle_id="bundle.missing",
            bundles={
                "bundle.demo": BundleEntry(
                    id="bundle.demo",
                    path="/bundles/bundle.demo",
                    module="entrypoint",
                )
            },
        )

    monkeypatch.setattr(bundle_registry, "_load_store_registry", _load_store_registry, raising=False)

    resolved = await bundle_registry.resolve_default_bundle_id_from_runtime_ctx(
        runtime_ctx,
        "tenant-a",
        "project-a",
    )

    assert resolved is None
