# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Unit tests for the shared distributed quota lock (funding_flow QuotaLock).

A minimal in-memory redis fake exercises SET NX acquire, the bounded spin-wait
timeout, and the compare-and-del release (own-token only)."""

from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.sdk.infra.economics.quota_lock import QuotaLock, quota_lock_key


class _FakeRedis:
    def __init__(self):
        self.store: dict = {}

    async def set(self, key, val, nx=False, ex=None, px=None):
        if nx and key in self.store:
            return None
        self.store[key] = val
        return True

    async def eval(self, lua, numkeys, key, token):
        # compare-and-del
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        self.store.pop(key, None)


def test_quota_lock_key_format():
    assert quota_lock_key("t", "p", "u1", "month", "__project__") == \
        "quota_lock:t:p:u1:month:__project__"


async def test_acquire_then_release_roundtrip():
    r = _FakeRedis()
    ql = QuotaLock(r)
    key = quota_lock_key("t", "p", "u1", "month", "__project__")
    assert await ql.acquire_blocking(key, ttl_sec=60, wait_total_sec=1.0) is True
    assert ql.acquired is True
    assert r.store.get(key) == ql.token       # we hold it
    assert await ql.release_if_held() is True  # released
    assert r.store == {}
    assert ql.acquired is False


async def test_acquire_times_out_when_contended():
    r = _FakeRedis()
    key = quota_lock_key("t", "p", "u1", "month", "__project__")
    r.store[key] = "someone-else"             # another holder owns it
    ql = QuotaLock(r)
    assert await ql.acquire_blocking(key, ttl_sec=60, wait_total_sec=0.2) is False
    assert ql.acquired is False
    assert r.store[key] == "someone-else"      # untouched (we never overwrote)


async def test_release_if_held_noop_when_not_acquired():
    ql = QuotaLock(_FakeRedis())
    assert await ql.release_if_held() is False


async def test_release_only_drops_own_token():
    r = _FakeRedis()
    key = quota_lock_key("t", "p", "u1", "month", "__project__")
    ql = QuotaLock(r)
    await ql.acquire_blocking(key, ttl_sec=60, wait_total_sec=1.0)
    # a successor overwrites the key (e.g. after our TTL) with a different token
    r.store[key] = "successor-token"
    assert await ql.release_if_held() is True   # we issued a release...
    assert r.store[key] == "successor-token"    # ...but compare-and-del kept theirs
