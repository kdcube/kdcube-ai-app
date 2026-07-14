# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""lg-solution's `custom` memory + KB drive KDCube's SHARED asyncpg pool directly.

The runtime bug this guards: the store used to bridge to a psycopg v3 DSN, but
psycopg is NOT installed in the chat processor ("No module named 'psycopg'"), so
memory + KB degraded to empty at runtime. KDCube's `pg_pool` is an asyncpg pool
(the SAME object `conv_index` uses) and asyncpg IS installed, so the store now
acquires from that pool directly — no psycopg.

These offline tests assert, with a fake asyncpg-like pool that records
`execute`/`fetch`/`fetchval`:
  - remember/recall + KB ingest/seed/search issue asyncpg-shaped SQL (`$1`
    placeholders, `pool.acquire()`) against a bundle-prefixed table in the ONE
    per-tenant/project schema, scoped by the (tenant, project, bundle_id, agent_id,
    user_id) COLUMNS, and
  - the DDL never `CREATE EXTENSION`s (the platform provides `vector`),
  - no `import psycopg` is reachable from the memory/KB modules,
  - with no pool the store degrades to empty recall / skipped writes (offline).
"""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
# ONE schema per tenant/project (shared by both agents); rows separated by columns.
SCHEMA = "kdcube_demo_tenant_demo_project"
MEMORIES = "ported_langgraph_agents_memories"
KB = "ported_langgraph_agents_kb"


def _module(name: str):
    _n, module = load_dynamic_module_for_path(BUNDLE_ROOT / "solution" / "lg_solution" / f"{name}.py")
    return module


def _scope():
    pg = _module("_pg")
    return pg.StorageScope(
        tenant="demo-tenant", project="demo-project",
        bundle_id="ported-langgraph-agents@2026-07-13", agent_id="lg-solution",
    )


# -- a minimal asyncpg-like pool that records every call ----------------------

class _FakeConn:
    def __init__(self, calls, fetch_rows, fetchval_value):
        self._calls = calls
        self._fetch_rows = fetch_rows
        self._fetchval_value = fetchval_value

    async def execute(self, sql, *args):
        self._calls.append(("execute", sql, args))
        return "OK"

    async def fetch(self, sql, *args):
        self._calls.append(("fetch", sql, args))
        return list(self._fetch_rows)

    async def fetchval(self, sql, *args):
        self._calls.append(("fetchval", sql, args))
        return self._fetchval_value


class _Acquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class FakePool:
    """Records the SQL a store issues; `acquire()` is an async context manager,
    exactly like `asyncpg.Pool.acquire()`."""

    def __init__(self, fetch_rows=(), fetchval_value=0):
        self.calls = []
        self._conn = _FakeConn(self.calls, fetch_rows, fetchval_value)

    def acquire(self):
        return _Acquire(self._conn)


def _executed_sql(pool: FakePool):
    return "\n".join(sql for kind, sql, _ in pool.calls if kind == "execute")


# -- custom memory drives the pool: bundle-prefixed table, column-scoped -------

def test_custom_memory_remember_issues_scoped_insert() -> None:
    memory = _module("memory")
    llm = _module("llm")
    cfg = llm.Config(openai_api_key=None)  # offline stub embeddings
    pool = FakePool()
    m = memory.build_memory(cfg, llm.LLMClient(cfg), pool=pool, schema=SCHEMA, scope=_scope())
    assert type(m).__name__ == "SemanticMemory"

    asyncio.run(m.remember("t:p:lg-solution:alice", "user likes trains"))

    inserts = [c for c in pool.calls if c[0] == "execute" and "INSERT INTO" in c[1]]
    assert inserts, pool.calls
    sql, args = inserts[0][1], inserts[0][2]
    # bundle-prefixed table in the shared schema + asyncpg $-placeholders + ::vector
    assert f'"{SCHEMA}".{MEMORIES}' in sql
    assert "$7::vector" in sql
    # scope columns are written: tenant, project, bundle_id, agent_id, user_id, text
    assert args[0] == "demo-tenant" and args[1] == "demo-project"
    assert args[2] == "ported-langgraph-agents@2026-07-13" and args[3] == "lg-solution"
    assert args[4] == "t:p:lg-solution:alice" and args[5] == "user likes trains"
    assert isinstance(args[6], str) and args[6].startswith("[")  # vector text literal
    # schema created via the same pool (no psycopg); NO CREATE EXTENSION
    executed = _executed_sql(pool)
    assert f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"' in executed
    assert "CREATE EXTENSION" not in executed


def test_custom_memory_recall_filters_by_full_scope() -> None:
    memory = _module("memory")
    llm = _module("llm")
    cfg = llm.Config(openai_api_key=None)
    pool = FakePool(fetch_rows=[{"text": "user likes trains", "score": 0.91}])
    m = memory.build_memory(cfg, llm.LLMClient(cfg), pool=pool, schema=SCHEMA, scope=_scope())

    hits = asyncio.run(m.recall("t:p:lg-solution:alice", "hobbies", k=5))

    fetches = [c for c in pool.calls if c[0] == "fetch"]
    assert fetches, pool.calls
    sql, args = fetches[0][1], fetches[0][2]
    assert f'"{SCHEMA}".{MEMORIES}' in sql and "$1::vector" in sql
    # WHERE tenant/project/bundle_id/agent_id/user_id — per-agent isolation by column
    assert "tenant = $2" in sql and "agent_id = $5" in sql and "user_id = $6" in sql
    assert args[1] == "demo-tenant" and args[3] == "ported-langgraph-agents@2026-07-13"
    assert args[4] == "lg-solution" and args[5] == "t:p:lg-solution:alice" and args[6] == 5
    assert len(hits) == 1 and hits[0].text == "user likes trains"
    assert abs(hits[0].score - 0.91) < 1e-9


# -- KB drives the pool: bundle-prefixed table, column-scoped ------------------

def test_kb_search_filters_by_scope() -> None:
    knowledge = _module("knowledge")
    llm = _module("llm")
    cfg = llm.Config(openai_api_key=None)
    pool = FakePool(fetch_rows=[{"title": "pgvector basics", "text": "…", "score": 0.8}])
    kb = knowledge.KnowledgeBase(cfg, llm.LLMClient(cfg), pool=pool, schema=SCHEMA, scope=_scope())

    hits = asyncio.run(kb.search("what is pgvector", k=4))

    fetches = [c for c in pool.calls if c[0] == "fetch"]
    assert fetches, pool.calls
    sql, args = fetches[0][1], fetches[0][2]
    assert f'"{SCHEMA}".{KB}' in sql and "$1::vector" in sql
    assert "tenant = $2" in sql and "agent_id = $5" in sql
    assert args[1] == "demo-tenant" and args[4] == "lg-solution" and args[5] == 4
    assert len(hits) == 1 and hits[0].title == "pgvector basics"


def test_kb_seed_ingests_when_empty_then_inserts() -> None:
    knowledge = _module("knowledge")
    llm = _module("llm")
    cfg = llm.Config(openai_api_key=None)
    pool = FakePool(fetchval_value=0)  # empty table -> seed ingests
    kb = knowledge.KnowledgeBase(cfg, llm.LLMClient(cfg), pool=pool, schema=SCHEMA, scope=_scope())

    n = asyncio.run(kb.seed())
    assert n > 0
    sql = _executed_sql(pool)
    assert f'"{SCHEMA}".{KB}' in sql
    assert "INSERT INTO" in sql and "ON CONFLICT (tenant, project, bundle_id, agent_id, title)" in sql
    assert "CREATE EXTENSION" not in sql
    # scoped count check ran against the bundle-prefixed table
    counts = [c for c in pool.calls if c[0] == "fetchval"]
    assert counts and f'"{SCHEMA}".{KB}' in counts[0][1]
    assert counts[0][2][0] == "demo-tenant" and counts[0][2][3] == "lg-solution"


def test_kb_seed_noop_when_already_populated() -> None:
    knowledge = _module("knowledge")
    llm = _module("llm")
    cfg = llm.Config(openai_api_key=None)
    pool = FakePool(fetchval_value=5)  # already populated -> no ingest
    kb = knowledge.KnowledgeBase(cfg, llm.LLMClient(cfg), pool=pool, schema=SCHEMA, scope=_scope())

    n = asyncio.run(kb.seed())
    assert n == 0
    assert not [c for c in pool.calls if c[0] == "execute" and "INSERT INTO" in c[1]]


# -- offline degradation (no pool) --------------------------------------------

def test_no_pool_degrades_to_empty_without_touching_a_driver() -> None:
    memory = _module("memory")
    knowledge = _module("knowledge")
    llm = _module("llm")
    cfg = llm.Config(openai_api_key=None)

    m = memory.build_memory(cfg, llm.LLMClient(cfg), pool=None, schema=None, scope=_scope())
    assert asyncio.run(m.recall("t:p:u", "anything", k=3)) == []
    asyncio.run(m.remember("t:p:u", "a note"))  # must not raise

    kb = knowledge.KnowledgeBase(cfg, llm.LLMClient(cfg), pool=None, schema=None, scope=_scope())
    assert asyncio.run(kb.search("q", k=3)) == []
    assert asyncio.run(kb.seed()) == 0
    assert asyncio.run(kb.ingest([knowledge.Doc("t", "body")])) == 0


# -- the negative assertion: memory/KB never import psycopg -------------------

def test_memory_and_kb_modules_do_not_import_psycopg() -> None:
    """No `import psycopg` / `from psycopg ...` anywhere (module-level OR lazy) in
    the memory/KB modules — the store drives asyncpg only. (The word may still
    appear in prose explaining the split; we assert on import statements.)"""
    import ast

    for name in ("memory", "knowledge", "_pg"):
        tree = ast.parse(inspect.getsource(_module(name)))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all("psycopg" not in a.name for a in node.names), name
            elif isinstance(node, ast.ImportFrom):
                assert node.module is None or "psycopg" not in node.module, name
