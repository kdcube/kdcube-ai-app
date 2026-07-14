# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""T2b economic ENFORCEMENT — the per-call (embedding) half, offline.

The turn-level guard is the economics base entrypoint's `run()` (budget preflight
+ rate limiter around the whole turn); that is a platform path exercised in a real
deploy with Redis + Postgres. These offline tests cover the PER-CALL half wired in
this bundle: retrieval/memory embeddings route through the host's
economics-guarded search facade when one is provided, the facade re-resolves per
call so its economics subject tracks the current turn, and the turn still runs
(stub embeddings) when economics is absent.

Tested at the deps/LLM seam — no DB, no API key, no real graph, no economics
runtime — via the dynamic module loader (the same seam the other bundle tests
use), so relative imports inside `solution/lg_solution/` resolve.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def _llm_module():
    _name, module = load_dynamic_module_for_path(BUNDLE_ROOT / "solution" / "lg_solution" / "llm.py")
    return module


def _deps_module():
    _name, module = load_dynamic_module_for_path(BUNDLE_ROOT / "solution" / "lg_solution" / "deps.py")
    return module


def _offline_config(llm):
    # Force the offline branch deterministically regardless of the ambient
    # OPENAI_API_KEY: no key -> the stub embedder / canned answers.
    return llm.Config(openai_api_key=None)


class _FakeGuardedFacade:
    """Stand-in for the economics-guarded `EconomicSearchModelService`: exposes
    the async `embed_texts` the guarded facade exposes, and records its calls."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts):
        self.calls.append(list(texts))
        # Vector length encodes text length, so the caller can tell it came here.
        return [[float(len(t)), 7.0] for t in texts]


def test_guarded_facade_used_when_provided_object() -> None:
    """A guarded facade passed directly (object form) is the embedding path."""
    llm = _llm_module()
    facade = _FakeGuardedFacade()
    client = llm.LLMClient(_offline_config(llm), embedding_service=facade)

    vecs = asyncio.run(client.embed(["ab", "cde"]))

    assert vecs == [[2.0, 7.0], [3.0, 7.0]]
    assert facade.calls == [["ab", "cde"]]


def test_guarded_facade_provider_reresolved_per_call() -> None:
    """A zero-arg provider (how the entrypoint wires it) is invoked fresh each
    embed, so the guard's economics subject tracks the current turn — a shared
    graph must not freeze the first turn's facade."""
    llm = _llm_module()
    built: list[_FakeGuardedFacade] = []

    def _provider():
        facade = _FakeGuardedFacade()
        built.append(facade)
        return facade

    client = llm.LLMClient(_offline_config(llm), embedding_service=_provider)

    asyncio.run(client.embed(["one"]))
    asyncio.run(client.embed(["two"]))

    # Re-resolved each call: two distinct facades, each used once.
    assert len(built) == 2
    assert built[0].calls == [["one"]]
    assert built[1].calls == [["two"]]


def test_turn_runs_offline_when_economics_absent() -> None:
    """No guarded facade, no models_service, no API key: the turn still runs on
    the deterministic offline stub (do not hard-fail on missing economics)."""
    llm = _llm_module()
    config = _offline_config(llm)
    client = llm.LLMClient(config, embedding_service=None)

    vecs = asyncio.run(client.embed(["hello", "world"]))

    # Deterministic unit vectors of the configured width — the stub path.
    assert len(vecs) == 2
    assert all(len(v) == config.embed_dim for v in vecs)
    # Same text -> same vector; different text -> different vector.
    assert vecs[0] == asyncio.run(client.embed(["hello"]))[0]
    assert vecs[0] != vecs[1]


def test_provider_returning_none_falls_back_to_stub() -> None:
    """A provider that degrades to None (economics off AND no models_service)
    must not break embedding — the client falls back to the offline stub."""
    llm = _llm_module()
    config = _offline_config(llm)
    client = llm.LLMClient(config, embedding_service=lambda: None)

    vecs = asyncio.run(client.embed(["x"]))
    assert len(vecs) == 1 and len(vecs[0]) == config.embed_dim


def test_build_deps_threads_embedding_service_into_llm() -> None:
    """`build_deps(embedding_service=...)` reaches the LLM client, so the graph's
    embed calls go through the guarded path."""
    deps_mod = _deps_module()
    provider = lambda: _FakeGuardedFacade()
    deps = deps_mod.build_deps(embedding_service=provider)
    assert deps.llm.embedding_service is provider
