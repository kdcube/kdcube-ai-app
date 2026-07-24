# SPDX-License-Identifier: MIT

"""The ``instr`` namespace: reads open, writes admin-gated, refs are wiring refs."""

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.named_service import (
    AgenticInstructionsNamedService,
)
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers.types import (
    OBJECT_DELETE,
    OBJECT_GET,
    OBJECT_LIST,
    OBJECT_UPSERT,
    NamedServiceContext,
    NamedServiceRequest,
)


class _FakeStore:
    def __init__(self):
        self.saved = []
        self.retired = []
        self.data = {
            "support-tone": {
                1: {
                    "instruction_id": "support-tone",
                    "version": 1,
                    "name": "Support tone",
                    "description": "",
                    "items": ["[TONE] be warm."],
                    "status": "active",
                    "created_by": "admin@example.test",
                    "created_at": None,
                    "updated_by": "",
                    "updated_at": None,
                }
            }
        }

    async def get(self, instruction_id, version=None):
        versions = self.data.get(instruction_id) or {}
        if not versions:
            return None
        v = int(version) if version is not None else max(versions)
        return versions.get(v)

    async def list_instructions(self, *, include_retired=False, q="", tags=None):
        return [versions[max(versions)] for versions in self.data.values()]

    async def list_versions(self, instruction_id):
        versions = self.data.get(instruction_id) or {}
        return [versions[v] for v in sorted(versions, reverse=True)]

    async def save_version(self, instruction_id, *, name, items, author, description="", tags=None, signals=None):
        if not str(name or "").strip():
            raise ValueError("name is required")
        self.saved.append((instruction_id, name, items, author))
        return {
            "instruction_id": instruction_id,
            "version": 2,
            "name": name,
            "description": description,
            "items": list(items or []),
            "status": "active",
            "created_by": author,
            "created_at": None,
            "updated_by": "",
            "updated_at": None,
        }

    async def retire(self, instruction_id, version=None, *, author):
        self.retired.append((instruction_id, version, author))
        return 1


def _provider(store):
    return AgenticInstructionsNamedService(store_factory=lambda tenant, project: store)


def _ctx(user_type="regular", roles=(), user_id="user-1"):
    return NamedServiceContext(
        tenant="demo", project="proj", user_id=user_id, user_type=user_type, roles=tuple(roles)
    )


@pytest.mark.asyncio
async def test_get_by_ref_returns_wire_object_with_versions():
    provider = _provider(_FakeStore())
    response = await provider.object_get(
        _ctx(),
        NamedServiceRequest(
            operation=OBJECT_GET, namespace="instr", object_ref="instr:custom:support-tone"
        ),
    )
    assert response.ok is True
    obj = response.ret["object"]
    assert obj["ref"] == "instr:custom:support-tone:1"
    assert obj["items"] == ["[TONE] be warm."]
    assert obj["created_by"] == "admin@example.test"
    assert obj["versions"][0]["version"] == 1


@pytest.mark.asyncio
async def test_get_unknown_and_malformed_refs_are_structured_errors():
    provider = _provider(_FakeStore())
    missing = await provider.object_get(
        _ctx(),
        NamedServiceRequest(
            operation=OBJECT_GET, namespace="instr", object_ref="instr:custom:ghost"
        ),
    )
    assert missing.ok is False and missing.error.code == "instruction_not_found"
    malformed = await provider.object_get(
        _ctx(),
        NamedServiceRequest(operation=OBJECT_GET, namespace="instr", object_ref="not-a-ref"),
    )
    assert malformed.ok is False and malformed.error.code == "instruction_ref_required"


@pytest.mark.asyncio
async def test_list_returns_latest_per_id():
    provider = _provider(_FakeStore())
    response = await provider.object_list(
        _ctx(), NamedServiceRequest(operation=OBJECT_LIST, namespace="instr")
    )
    assert response.ok is True
    assert [o["ref"] for o in response.ret["items"]] == ["instr:custom:support-tone:1"]


@pytest.mark.asyncio
async def test_writes_are_admin_gated():
    store = _FakeStore()
    provider = _provider(store)
    denied = await provider.object_upsert(
        _ctx(user_type="regular"),
        NamedServiceRequest(
            operation=OBJECT_UPSERT,
            namespace="instr",
            payload={"instruction_id": "support-tone", "name": "n", "items": ["x"]},
        ),
    )
    assert denied.ok is False and denied.error.code == "admin_required"
    denied_delete = await provider.object_delete(
        _ctx(user_type="regular"),
        NamedServiceRequest(
            operation=OBJECT_DELETE, namespace="instr", object_ref="instr:custom:support-tone"
        ),
    )
    assert denied_delete.ok is False and denied_delete.error.code == "admin_required"
    assert store.saved == [] and store.retired == []


@pytest.mark.asyncio
async def test_admin_upsert_saves_next_version_with_provenance():
    store = _FakeStore()
    provider = _provider(store)
    response = await provider.object_upsert(
        _ctx(user_type="admin", user_id="admin@example.test"),
        NamedServiceRequest(
            operation=OBJECT_UPSERT,
            namespace="instr",
            object_ref="instr:custom:support-tone",
            payload={"name": "Support tone", "items": ["[TONE] be crisp."]},
        ),
    )
    assert response.ok is True
    obj = response.ret["object"]
    assert obj["ref"] == "instr:custom:support-tone:2"
    assert obj["created_by"] == "admin@example.test"
    assert store.saved[0][3] == "admin@example.test"
    # validation errors surface as structured 400s
    invalid = await provider.object_upsert(
        _ctx(user_type="admin"),
        NamedServiceRequest(
            operation=OBJECT_UPSERT,
            namespace="instr",
            payload={"instruction_id": "support-tone", "items": ["x"]},
        ),
    )
    assert invalid.ok is False and invalid.error.code == "instruction_invalid"


@pytest.mark.asyncio
async def test_admin_delete_retires_pinned_or_all_versions():
    store = _FakeStore()
    provider = _provider(store)
    pinned = await provider.object_delete(
        _ctx(roles=("admin",)),
        NamedServiceRequest(
            operation=OBJECT_DELETE, namespace="instr", object_ref="instr:custom:support-tone:1"
        ),
    )
    assert pinned.ok is True
    assert store.retired[-1][:2] == ("support-tone", 1)
    unpinned = await provider.object_delete(
        _ctx(user_type="super_admin"),
        NamedServiceRequest(
            operation=OBJECT_DELETE, namespace="instr", object_ref="instr:custom:support-tone"
        ),
    )
    assert unpinned.ok is True
    assert store.retired[-1][:2] == ("support-tone", None)
