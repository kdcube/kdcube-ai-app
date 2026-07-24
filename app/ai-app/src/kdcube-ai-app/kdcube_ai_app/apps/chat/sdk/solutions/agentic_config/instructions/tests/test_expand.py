# SPDX-License-Identifier: MIT

"""Async expansion of stored custom refs into composer tokens."""

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions import (
    compose_instruction_body,
    expand_instruction_items,
    has_custom_instruction_refs,
)


class _FakeStore:
    """Dict-backed store: {(id): {version: [items]}}; latest = max version."""

    def __init__(self, data):
        self._data = data

    async def get(self, instruction_id, version=None):
        versions = self._data.get(instruction_id)
        if not versions:
            return None
        v = int(version) if version is not None else max(versions)
        if v not in versions:
            return None
        return {"instruction_id": instruction_id, "version": v, "items": list(versions[v])}


@pytest.mark.asyncio
async def test_expansion_replaces_refs_in_place_and_passes_others_through():
    store = _FakeStore({"tone": {1: ["[TONE] be terse."], 2: ["[TONE] be warm."]}})
    out = await expand_instruction_items(
        ["REACT_LITE_SKILLS", "instr:custom:tone", "literal tail"], store=store
    )
    # unpinned -> latest version
    assert out == ["REACT_LITE_SKILLS", "[TONE] be warm.", "literal tail"]
    pinned = await expand_instruction_items(["instr:custom:tone:1"], store=store)
    assert pinned == ["[TONE] be terse."]


@pytest.mark.asyncio
async def test_nested_refs_expand_recursively():
    store = _FakeStore(
        {
            "outer": {1: ["[OUTER-HEAD]", "instr:custom:inner", "[OUTER-TAIL]"]},
            "inner": {1: ["[INNER]"]},
        }
    )
    out = await expand_instruction_items(["instr:custom:outer"], store=store)
    assert out == ["[OUTER-HEAD]", "[INNER]", "[OUTER-TAIL]"]


@pytest.mark.asyncio
async def test_cycles_and_unknown_refs_drop_without_leaking():
    store = _FakeStore(
        {
            "a": {1: ["[A]", "instr:custom:b"]},
            "b": {1: ["[B]", "instr:custom:a"]},  # cycle back to a
        }
    )
    out = await expand_instruction_items(["instr:custom:a", "instr:custom:ghost"], store=store)
    assert out == ["[A]", "[B]"]  # the cyclic re-entry and the unknown ref vanish
    # and the expanded list composes cleanly
    assert compose_instruction_body(out) == "[A]\n\n[B]"


@pytest.mark.asyncio
async def test_store_error_drops_the_ref_only():
    class _Boom:
        async def get(self, *_a, **_k):
            raise RuntimeError("db down")

    out = await expand_instruction_items(
        ["REACT_LITE_SKILLS", "instr:custom:tone"], store=_Boom()
    )
    assert out == ["REACT_LITE_SKILLS"]


def test_has_custom_instruction_refs():
    assert has_custom_instruction_refs(["a", "instr:custom:x"])
    assert has_custom_instruction_refs("instr:custom:x:2")
    assert not has_custom_instruction_refs(["instr:profile:lite", "literal"])
    assert not has_custom_instruction_refs(None)
