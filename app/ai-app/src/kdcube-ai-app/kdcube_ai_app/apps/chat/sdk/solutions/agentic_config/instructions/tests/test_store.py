# SPDX-License-Identifier: MIT

"""AgenticInstructionsStore: validation, immutability contract, SQL surface.

These tests run against a fake asyncpg-like pool — they pin the store's
validation rules, provenance requirements, and the statements it issues.
Live-database behavior is covered by the deploy schema + env testing.
"""

import json

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.store import (
    INSTRUCTIONS_TABLE,
    AgenticInstructionsStore,
)


class _FakeCon:
    def __init__(self, log):
        self._log = log

    async def execute(self, sql, *params):
        self._log.append(("execute", " ".join(sql.split()), params))
        return "UPDATE 1"

    async def fetchrow(self, sql, *params):
        self._log.append(("fetchrow", " ".join(sql.split()), params))
        return {
            "instruction_id": params[0] if params else "",
            "version": 1,
            "name": params[1] if len(params) > 1 else "",
            "items": params[3] if len(params) > 3 else "[]",
            "status": "active",
        }

    async def fetch(self, sql, *params):
        self._log.append(("fetch", " ".join(sql.split()), params))
        return []


class _FakeAcquire:
    def __init__(self, log):
        self._log = log

    async def __aenter__(self):
        return _FakeCon(self._log)

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self):
        self.log = []

    def acquire(self):
        return _FakeAcquire(self.log)


def _store(pool):
    return AgenticInstructionsStore(pg_pool=pool, tenant="demo-tenant", project="demo-project")


def test_schema_name_derives_from_scope():
    store = _store(_FakePool())
    assert store.schema == "kdcube_demo_tenant_demo_project"


@pytest.mark.asyncio
async def test_save_version_validates_and_inserts_next_version():
    pool = _FakePool()
    store = _store(pool)
    record = await store.save_version(
        "Support-Tone",  # normalized to lowercase slug
        name="Support tone",
        items=["[TONE] be warm.", "  ", "REACT_LITE_SKILLS"],
        author="admin@example.test",
    )
    assert record["instruction_id"] == "support-tone"
    op, sql, params = pool.log[-1]
    assert op == "fetchrow"
    assert f"INSERT INTO {store.schema}.{INSTRUCTIONS_TABLE}" in sql
    assert "COALESCE(( SELECT MAX(version)" in sql  # next-version, never overwrite
    assert "UPDATE" not in sql                       # immutable versions
    assert json.loads(params[3]) == ["[TONE] be warm.", "REACT_LITE_SKILLS"]  # empties dropped
    assert params[4] == "admin@example.test"


@pytest.mark.asyncio
async def test_save_version_requires_slug_name_author_items():
    store = _store(_FakePool())
    with pytest.raises(ValueError):
        await store.save_version("Bad Slug!", name="n", items=["x"], author="a")
    with pytest.raises(ValueError):
        await store.save_version("ok-id", name="", items=["x"], author="a")
    with pytest.raises(ValueError):
        await store.save_version("ok-id", name="n", items=["x"], author="")
    with pytest.raises(ValueError):
        await store.save_version("ok-id", name="n", items=[], author="a")
    with pytest.raises(ValueError):
        await store.save_version("ok-id", name="n", items=["", "  "], author="a")


@pytest.mark.asyncio
async def test_retire_requires_author_and_flips_status_only():
    pool = _FakePool()
    store = _store(pool)
    with pytest.raises(ValueError):
        await store.retire("ok-id", author="")
    count = await store.retire("ok-id", 2, author="admin@example.test")
    assert count == 1
    op, sql, params = pool.log[-1]
    assert op == "execute"
    assert "SET status = $2, updated_by = $3, updated_at = now()" in sql
    assert "AND version = $4" in sql
    assert params == ("ok-id", "retired", "admin@example.test", 2)


@pytest.mark.asyncio
async def test_get_pinned_ignores_status_unpinned_wants_active():
    pool = _FakePool()
    store = _store(pool)
    await store.get("ok-id", 3)
    _, pinned_sql, pinned_params = pool.log[-1]
    assert "status" not in pinned_sql       # a pinned version resolves even when retired
    assert pinned_params == ("ok-id", 3)
    await store.get("ok-id")
    _, latest_sql, latest_params = pool.log[-1]
    assert "status = $2" in latest_sql      # unpinned latest filters to active
    assert "ORDER BY version DESC LIMIT 1" in latest_sql
    assert latest_params == ("ok-id", "active")


@pytest.mark.asyncio
async def test_missing_pool_raises():
    store = AgenticInstructionsStore(tenant="t", project="p")
    with pytest.raises(RuntimeError):
        await store.get("ok-id")
