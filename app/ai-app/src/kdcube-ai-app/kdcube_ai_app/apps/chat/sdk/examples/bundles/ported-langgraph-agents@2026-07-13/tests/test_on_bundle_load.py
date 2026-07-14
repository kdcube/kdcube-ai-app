"""`on_bundle_load` provisions the memory + KB storage at load.

The entrypoint's `on_bundle_load` is the PRIMARY provisioning path (the stores'
lazy `_prepare` stays as an idempotent fallback). These tests assert it issues the
bundle-level DDL — the ONE `kdcube_{tenant}_{project}` schema + BOTH bundle-prefixed
tables — with `IF NOT EXISTS` and never `CREATE EXTENSION`, and that it skips
cleanly offline (no pool). A fake asyncpg pool records the executed SQL; no DB, no
API key, no heavy deps.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "kdcube_demo_tenant_demo_project"


def _module(rel: str):
    _n, module = load_dynamic_module_for_path(BUNDLE_ROOT / rel)
    return module


class _FakeConn:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def execute(self, sql: str, *args) -> None:
        self._log.append(sql)


class _FakeAcquire:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *exc) -> bool:
        return False


class _FakePool:
    """Minimal asyncpg-pool stand-in: `acquire()` yields a connection that records
    every executed statement."""

    def __init__(self) -> None:
        self.sql: list[str] = []

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(_FakeConn(self.sql))


def _make_instance(monkeypatch, *, pg_pool):
    from kdcube_ai_app.infra.service_hub.inventory import Config as InvConfig
    from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint import BaseEntrypoint

    # Neutralize the base hook (named-services discovery / UI build / public-content
    # indexes) — this test targets only the memory/KB provisioning this bundle adds.
    async def _noop(self, **kwargs):
        return None

    monkeypatch.setattr(BaseEntrypoint, "on_bundle_load", _noop)

    ep_mod = _module("entrypoint.py")
    inst = ep_mod.LGPortedAgentsBundle(config=InvConfig(), pg_pool=pg_pool, redis=None)
    monkeypatch.setattr(inst, "runtime_identity", lambda: {"tenant": "demo-tenant", "project": "demo-project"})
    monkeypatch.setattr(inst, "_named_services_bundle_id", lambda: ep_mod.BUNDLE_ID)
    return ep_mod, inst


def test_on_bundle_load_provisions_the_shared_schema_and_both_tables(monkeypatch) -> None:
    pool = _FakePool()
    _ep_mod, inst = _make_instance(monkeypatch, pg_pool=pool)

    asyncio.run(inst.on_bundle_load(pg_pool=pool))

    joined = "\n".join(pool.sql)

    # The ONE per-tenant/project schema — created once, not per agent.
    assert f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"' in joined
    assert joined.count(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"') == 2  # memory + KB ensure

    # BOTH bundle-prefixed tables, IF NOT EXISTS, in the shared schema.
    assert f'CREATE TABLE IF NOT EXISTS "{SCHEMA}".ported_langgraph_agents_memories' in joined
    assert f'CREATE TABLE IF NOT EXISTS "{SCHEMA}".ported_langgraph_agents_kb' in joined

    # The memory scope index is created; agent_id is a COLUMN, never a schema/table.
    assert "ported_langgraph_agents_memories_scope_idx" in joined
    assert "__lg_solution" not in joined and "__lg_react" not in joined

    # The platform PostgresSetup job owns the extension — the bundle never creates it.
    assert "CREATE EXTENSION" not in joined


def test_on_bundle_load_skips_cleanly_when_no_pool(monkeypatch) -> None:
    _ep_mod, inst = _make_instance(monkeypatch, pg_pool=None)

    called = {"identity": False}
    monkeypatch.setattr(inst, "runtime_identity", lambda: called.__setitem__("identity", True) or {})

    # No pool anywhere (self.pg_pool is None, no kwarg) → returns without touching
    # storage and without resolving identity.
    asyncio.run(inst.on_bundle_load())

    assert called["identity"] is False
