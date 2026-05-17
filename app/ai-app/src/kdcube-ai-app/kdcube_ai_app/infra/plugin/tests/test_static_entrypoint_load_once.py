# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio

import pytest

from kdcube_ai_app.infra.plugin.agentic_loader import (
    _bundle_static_entrypoint_load_done,
    _bundle_static_entrypoint_load_tasks,
    clear_agentic_caches,
    run_static_bundle_entrypoint_load_once,
)


async def _wait_until(predicate, *, timeout: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("timed out waiting for condition")
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_static_entrypoint_load_cleanup_marks_done_after_waiter_cancellation():
    clear_agentic_caches()
    load_key = "test::static-entrypoint::success"
    started = asyncio.Event()
    finish = asyncio.Event()
    calls = 0

    async def _load():
        nonlocal calls
        calls += 1
        started.set()
        await finish.wait()

    waiter = asyncio.create_task(
        run_static_bundle_entrypoint_load_once(
            load_key=load_key,
            load_coro_factory=_load,
        )
    )
    await started.wait()
    assert load_key in _bundle_static_entrypoint_load_tasks

    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter

    assert load_key in _bundle_static_entrypoint_load_tasks
    finish.set()

    await _wait_until(lambda: load_key not in _bundle_static_entrypoint_load_tasks)
    assert load_key in _bundle_static_entrypoint_load_done
    assert calls == 1

    clear_agentic_caches()

@pytest.mark.asyncio
async def test_static_entrypoint_load_cleanup_allows_retry_after_cancelled_waiter_and_failure():
    clear_agentic_caches()
    load_key = "test::static-entrypoint::failure"
    started = asyncio.Event()
    finish = asyncio.Event()
    calls = 0

    async def _load():
        nonlocal calls
        calls += 1
        started.set()
        await finish.wait()
        raise RuntimeError("load failed")

    waiter = asyncio.create_task(
        run_static_bundle_entrypoint_load_once(
            load_key=load_key,
            load_coro_factory=_load,
        )
    )
    await started.wait()
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter

    finish.set()

    await _wait_until(lambda: load_key not in _bundle_static_entrypoint_load_tasks)
    assert load_key not in _bundle_static_entrypoint_load_done
    assert calls == 1

    clear_agentic_caches()
