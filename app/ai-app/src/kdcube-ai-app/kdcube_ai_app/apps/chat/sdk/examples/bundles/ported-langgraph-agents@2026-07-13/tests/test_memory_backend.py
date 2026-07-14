# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""Long-term memory is a PLUGGABLE BACKEND — the demo ships two ways of doing
LangGraph long-term memory, config-selectable via `LG_MEMORY_BACKEND`:

  - "custom"          -> `SemanticMemory` (hand-rolled async pgvector table)
  - "langgraph_store" -> `StoreMemory`    (LangGraph-native AsyncPostgresStore)

These offline tests cover the seam the graph relies on: `build_memory(config, llm)`
selects the right backend, both honor the async `Memory` interface, and both
degrade to empty recall with no DB (the store degrades internally to `[]`; the
custom backend degrades at the graph's `retrieve` node, exercised end to end).

Tested via the dynamic module loader (the same seam the other bundle tests use)
so the relative imports inside `solution/lg_solution/` resolve — no DB, no API key.
"""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def _module(name: str):
    _n, module = load_dynamic_module_for_path(BUNDLE_ROOT / "solution" / "lg_solution" / f"{name}.py")
    return module


def _offline_deps(backend: str):
    """Build the graph's Deps offline, forcing a backend + an unreachable DB.

    `openai_api_key=None` forces the stub embedder/answers; the bogus
    `database_url` guarantees no store or table is reachable, so we observe
    degradation rather than real persistence."""
    deps_mod = _module("deps")
    cfg = deps_mod.Config(
        openai_api_key=None,
        memory_backend=backend,
        database_url="postgresql://nope:nope@127.0.0.1:1/none",
    )
    return deps_mod, deps_mod.build_deps(config=cfg)


# -- selection ---------------------------------------------------------------

def test_build_memory_defaults_to_custom() -> None:
    memory = _module("memory")
    llm = _module("llm")
    cfg = llm.Config(openai_api_key=None)  # memory_backend defaults to "custom"
    m = memory.build_memory(cfg, llm.LLMClient(cfg))
    assert type(m).__name__ == "SemanticMemory"
    assert isinstance(m, memory.Memory)


def test_build_memory_selects_langgraph_store() -> None:
    memory = _module("memory")
    llm = _module("llm")
    cfg = llm.Config(openai_api_key=None, memory_backend="langgraph_store")
    m = memory.build_memory(cfg, llm.LLMClient(cfg))
    assert type(m).__name__ == "StoreMemory"
    assert isinstance(m, memory.Memory)


def test_unrecognized_backend_falls_back_to_custom() -> None:
    memory = _module("memory")
    llm = _module("llm")
    cfg = llm.Config(openai_api_key=None, memory_backend="bogus")
    m = memory.build_memory(cfg, llm.LLMClient(cfg))
    assert type(m).__name__ == "SemanticMemory"


# -- interface ---------------------------------------------------------------

def test_both_backends_expose_async_remember_recall() -> None:
    memory = _module("memory")
    llm = _module("llm")
    for backend in ("custom", "langgraph_store"):
        cfg = llm.Config(openai_api_key=None, memory_backend=backend)
        m = memory.build_memory(cfg, llm.LLMClient(cfg))
        assert inspect.iscoroutinefunction(m.remember)
        assert inspect.iscoroutinefunction(m.recall)


# -- offline degradation -----------------------------------------------------

def test_store_backend_recall_degrades_offline() -> None:
    """No AsyncPostgresStore / no DB -> empty recall + no-op write, in-backend."""
    memory = _module("memory")
    llm = _module("llm")
    cfg = llm.Config(
        openai_api_key=None,
        memory_backend="langgraph_store",
        database_url="postgresql://nope:nope@127.0.0.1:1/none",
    )
    m = memory.build_memory(cfg, llm.LLMClient(cfg))
    assert asyncio.run(m.recall("t:p:u", "anything", k=3)) == []
    asyncio.run(m.remember("t:p:u", "a note"))  # must not raise


def test_both_backends_yield_empty_recall_through_the_graph_offline() -> None:
    """A full offline turn degrades to empty memories + a stub answer for BOTH
    backends — the store internally, the custom backend at the retrieve node —
    without crashing the turn. graph.py is unchanged; the backend is transparent."""
    graph_mod = _module("graph")
    for backend in ("custom", "langgraph_store"):
        _deps_mod, deps = _offline_deps(backend)
        graph = graph_mod.build_graph(deps)
        out = asyncio.run(
            graph.ainvoke(
                {
                    "messages": [],
                    "user_id": "t:p:u",
                    "question": "How do LangGraph checkpointers persist state across restarts?",
                }
            )
        )
        assert out["memories"] == [], (backend, out["memories"])
        assert out["answer"], backend
