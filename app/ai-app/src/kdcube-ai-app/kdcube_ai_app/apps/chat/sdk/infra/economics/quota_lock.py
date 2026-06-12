# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

# chat/sdk/infra/economics/quota_lock.py
"""
Distributed quota lock: serializes the admit->reserve window for a single subject
so concurrent requests don't double-count a shared-pool reservation.

Extracted so ONE implementation backs BOTH the chat run() path and the reusable
EconomicsGuard. The redis mechanics (SET NX acquire with a px fallback, and the
compare-and-del Lua release with a python fallback) plus the bounded spin-wait
live here. Callers own the policy gating (enforce flag / admin bypass /
redis-absent), the denial they raise on timeout, and their own log lines — those
differ per surface and stay in the caller.
"""

from __future__ import annotations

import asyncio
import secrets
from typing import Any, Optional


def quota_lock_key(tenant: str, project: str, user_id: str, scope: str, bundle_id: str) -> str:
    """Per-subject, per-scope lock key (bundle_id is the global RL subject bundle)."""
    return f"quota_lock:{tenant}:{project}:{user_id}:{scope}:{bundle_id}"


class QuotaLock:
    """A single-hold distributed lock. One instance per request/turn: it remembers
    the key+token it took so release() only drops a lock WE still own (a release
    after our TTL expired can't evict a successor)."""

    def __init__(self, redis: Any):
        self.redis = redis
        self.key: Optional[str] = None
        self.token: Optional[str] = None
        self.acquired: bool = False

    async def acquire_blocking(self, key: str, *, ttl_sec: int, wait_total_sec: float) -> bool:
        """Spin-wait up to wait_total_sec to take `key`. Returns True if acquired,
        False on timeout. Precondition: redis is present (callers gate on
        redis-absent / policy / bypass and skip calling this)."""
        self.key = key
        self.token = secrets.token_hex(16)
        t0 = asyncio.get_event_loop().time()
        sleep = 0.05
        while True:
            if await self._try_acquire(self.key, self.token, ttl_sec):
                self.acquired = True
                return True
            if (asyncio.get_event_loop().time() - t0) >= wait_total_sec:
                return False
            await asyncio.sleep(sleep)
            sleep = min(sleep * 1.5, 0.25)

    async def release_if_held(self) -> bool:
        """Release the lock if we still hold it. Returns True if a release was
        issued (so the caller can log it), False otherwise. Always clears state."""
        held = bool(self.acquired and self.key and self.token)
        if held:
            await self._release(self.key, self.token)
        self.key = None
        self.token = None
        self.acquired = False
        return held

    # -- redis mechanics ------------------------------------------------------
    async def _try_acquire(self, key: str, token: str, ttl_sec: int) -> bool:
        r = self.redis
        if r is None:
            return False
        try:
            return bool(await r.set(key, token, nx=True, ex=ttl_sec))
        except TypeError:
            pass
        except Exception:
            return False
        try:
            return bool(await r.set(key, token, nx=True, px=int(ttl_sec * 1000)))
        except Exception:
            return False

    async def _release(self, key: str, token: str) -> None:
        r = self.redis
        if r is None:
            return
        # compare-and-del: only release if WE still hold it (token match).
        lua = (
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end"
        )
        try:
            await r.eval(lua, 1, key, token)
            return
        except TypeError:
            try:
                await r.eval(lua, keys=[key], args=[token])
                return
            except Exception:
                pass
        except Exception:
            pass
        try:
            cur = await r.get(key)
            if cur is None:
                return
            if isinstance(cur, (bytes, bytearray)):
                cur = cur.decode("utf-8", errors="ignore")
            if str(cur) == str(token):
                await r.delete(key)
        except Exception:
            pass
