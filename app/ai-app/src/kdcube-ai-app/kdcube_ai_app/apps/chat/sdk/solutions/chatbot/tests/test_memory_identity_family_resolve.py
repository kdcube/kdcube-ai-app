"""The memory mixin resolves the identity family server-side for READ scoping."""

from __future__ import annotations

import types

import pytest

import kdcube_ai_app.apps.chat.sdk.infra.bundle_operations as bundle_operations
from kdcube_ai_app.apps.chat.sdk.context.memory.models import MemoryScope
from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint_with_memory import (
    MemoryEntrypointMixin,
)


_ACTOR = "02e53484-actor"
_LINKED = "telegram_434804821"


class _Logger:
    def log(self, *args, **kwargs):
        return None


class _Stub:
    """Minimal carrier exposing only what _memory_read_user_ids touches."""

    def __init__(self, *, enabled: bool, resolve):
        self._enabled = enabled
        self._resolve = resolve
        self.logger = _Logger()

    _memory_read_user_ids = MemoryEntrypointMixin._memory_read_user_ids

    def _memory_scope(self):
        return MemoryScope(tenant="t", project="p", user_id=_ACTOR, bundle_id="b@1")

    def _memory_identity_family_enabled(self) -> bool:
        return self._enabled

    def _memory_identity_family_bundle_id(self) -> str:
        return "connection-hub@1-0"


@pytest.fixture(autouse=True)
def _patch_call(monkeypatch):
    holder = {}

    async def _fake_call(**kwargs):
        holder["called_with"] = kwargs
        resolve = holder["resolve"]
        if isinstance(resolve, Exception):
            raise resolve
        return resolve

    monkeypatch.setattr(bundle_operations, "call_bundle_operation", _fake_call)
    return holder


@pytest.mark.asyncio
async def test_resolves_family_from_memory_user_ids(_patch_call) -> None:
    _patch_call["resolve"] = {
        "ok": True,
        "linked": True,
        "memory_user_ids": [_ACTOR, _LINKED],
    }
    stub = _Stub(enabled=True, resolve=None)
    family = await stub._memory_read_user_ids()
    assert family == [_ACTOR, _LINKED]
    # Resolved for the CURRENT actor, in-process, against Connection Hub.
    assert _patch_call["called_with"]["operation"] == "identity_family_resolve"
    assert _patch_call["called_with"]["bundle_id"] == "connection-hub@1-0"
    assert _patch_call["called_with"]["data"] == {}


@pytest.mark.asyncio
async def test_unlinked_actor_returns_none(_patch_call) -> None:
    # Resolver returns just the actor (one-item family) -> single-user path.
    _patch_call["resolve"] = {"ok": True, "linked": False, "memory_user_ids": [_ACTOR]}
    stub = _Stub(enabled=True, resolve=None)
    assert await stub._memory_read_user_ids() is None


@pytest.mark.asyncio
async def test_resolver_failure_falls_back_to_none(_patch_call) -> None:
    # A resolver error must never error the read; fall back to single-actor.
    _patch_call["resolve"] = RuntimeError("connection hub down")
    stub = _Stub(enabled=True, resolve=None)
    assert await stub._memory_read_user_ids() is None


@pytest.mark.asyncio
async def test_disabled_skips_resolution(_patch_call) -> None:
    _patch_call["resolve"] = {"memory_user_ids": [_ACTOR, _LINKED]}
    stub = _Stub(enabled=False, resolve=None)
    assert await stub._memory_read_user_ids() is None
    # When disabled, the cross-bundle call is not even attempted.
    assert "called_with" not in _patch_call


@pytest.mark.asyncio
async def test_family_always_includes_actor(_patch_call) -> None:
    # Even if the resolver omits the actor, it is included for the read scope.
    _patch_call["resolve"] = {"memory_user_ids": [_LINKED]}
    stub = _Stub(enabled=True, resolve=None)
    assert await stub._memory_read_user_ids() == [_ACTOR, _LINKED]
