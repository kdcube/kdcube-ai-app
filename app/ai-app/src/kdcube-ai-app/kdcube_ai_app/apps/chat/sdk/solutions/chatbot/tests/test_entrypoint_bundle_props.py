import copy
from types import SimpleNamespace

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint import BaseEntrypoint


class _EntrypointForPropsTest(BaseEntrypoint):
    def configuration_defaults(self):
        return {
            "ui": {
                "widgets": {
                    "alpha": {
                        "enabled": True,
                        "src_folder": "ui/widgets/alpha",
                        "build_command": "npm run build",
                    },
                    "beta": {
                        "enabled": True,
                        "src_folder": "ui/widgets/beta",
                        "build_command": "npm run build",
                    },
                },
            },
        }

    @property
    def configuration(self):
        return self._deep_merge_props(self.configuration_defaults(), self.bundle_props or {})

    async def _ensure_ui_build(self):
        self.props_seen_by_ui_build = copy.deepcopy(self.bundle_props)


@pytest.mark.asyncio
async def test_on_bundle_load_refreshes_effective_props_before_ui_build(monkeypatch):
    async def _get_bundle_props(redis, *, tenant, project, bundle_id):
        assert redis == "redis"
        assert tenant == "tenant-a"
        assert project == "project-a"
        assert bundle_id == "bundle@1"
        return {
            "ui": {
                "widgets": {
                    "alpha": {
                        "enabled": False,
                    },
                },
            },
        }

    monkeypatch.setattr(
        "kdcube_ai_app.infra.plugin.bundle_store.get_bundle_props",
        _get_bundle_props,
    )

    entrypoint = _EntrypointForPropsTest.__new__(_EntrypointForPropsTest)
    entrypoint.bundle_props = {}
    entrypoint.redis = "redis"
    entrypoint.kv_cache = None
    entrypoint.runtime_ctx = None
    entrypoint._comm_context = SimpleNamespace(
        actor=SimpleNamespace(tenant_id="tenant-a", project_id="project-a")
    )
    entrypoint.config = SimpleNamespace(
        ai_bundle_spec=SimpleNamespace(id="bundle@1"),
        role_models={},
        set_role_models=lambda value: None,
        set_embedding=lambda value: None,
    )

    await entrypoint.on_bundle_load()

    widgets = entrypoint.props_seen_by_ui_build["ui"]["widgets"]
    assert widgets["alpha"]["enabled"] is False
    assert widgets["alpha"]["src_folder"] == "ui/widgets/alpha"
    assert widgets["beta"]["enabled"] is True
    assert widgets["beta"]["src_folder"] == "ui/widgets/beta"


def test_bundle_prop_model_overrides_rebuild_model_service():
    entrypoint = _EntrypointForPropsTest.__new__(_EntrypointForPropsTest)
    entrypoint.bundle_props = {
        "role_models": {
            "answer_generator": {
                "provider": "anthropic",
                "model": "claude-test",
            },
        },
        "embedding": {
            "embedder_id": "openai-text-embedding-3-small",
        },
    }
    entrypoint.config = SimpleNamespace(
        role_models={},
        set_role_models=lambda value: setattr(entrypoint, "role_models_seen", value),
        set_embedding=lambda value: setattr(entrypoint, "embedding_seen", value),
    )
    entrypoint.models_service = object()
    entrypoint.rebuild_count = 0

    def _rebuild_models_service():
        entrypoint.rebuild_count += 1
        entrypoint.models_service = object()

    entrypoint._rebuild_models_service = _rebuild_models_service

    entrypoint._apply_bundle_props_overrides()

    assert entrypoint.role_models_seen["answer_generator"]["model"] == "claude-test"
    assert entrypoint.embedding_seen["embedder_id"] == "openai-text-embedding-3-small"
    assert entrypoint.rebuild_count == 1
