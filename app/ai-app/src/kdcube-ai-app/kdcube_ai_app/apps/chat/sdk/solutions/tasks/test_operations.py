from __future__ import annotations

from types import SimpleNamespace

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.tasks import operations
from kdcube_ai_app.apps.chat.sdk.solutions.tasks.storage import TaskStorage


def _entrypoint() -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(
            tenant="demo-tenant",
            project="demo-project",
            ai_bundle_spec=SimpleNamespace(id="bundle@1-0"),
        ),
        settings=SimpleNamespace(TENANT="demo-tenant", PROJECT="demo-project"),
    )


def _configure(tmp_path) -> None:
    operations.configure_task_operations(
        storage_root_or_error=lambda _entrypoint: str(tmp_path),
        target_user_id=lambda _entrypoint, user_id=None, fingerprint=None: user_id or fingerprint or "user-a",
        bundle_id="bundle@1-0",
    )


@pytest.mark.asyncio
async def test_scheduled_execution_skips_task_deleted_after_enqueue(tmp_path):
    _configure(tmp_path)
    storage = TaskStorage(tmp_path, user_id="user-a")
    task = storage.create_task(title="Inbox monitor", schedule_cron="*/10 * * * *")
    execution = storage.create_execution(
        task_id=task["id"],
        status="queued",
        trigger="scheduled",
        source={"due_slot": "2026-05-08T08:49:00+00:00"},
        conversation_id="task_job_1",
    )
    storage.delete_task(task_id=task["id"])

    result = await operations.run_task_execution(
        _entrypoint(),
        task_id=task["id"],
        trigger="scheduled",
        source={"due_slot": "2026-05-08T08:49:00+00:00"},
        execution_id=execution["id"],
        user_id="user-a",
    )

    updated = storage.get_execution(execution_id=execution["id"], task_id=task["id"])
    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "task_not_runnable"
    assert result["task"]["status"] == "deleted"
    assert updated["status"] == "cancelled"
    assert "task status is deleted" in updated["summary"]


@pytest.mark.asyncio
async def test_scheduled_execution_skips_disabled_task_at_pickup(tmp_path):
    _configure(tmp_path)
    storage = TaskStorage(tmp_path, user_id="user-a")
    task = storage.create_task(title="Inbox monitor", schedule_cron="*/10 * * * *")
    storage.set_task_status(task_id=task["id"], status="disabled")
    execution = storage.create_execution(task_id=task["id"], status="queued", trigger="scheduled")

    result = await operations.run_task_execution(
        _entrypoint(),
        task_id=task["id"],
        trigger="Scheduled",
        source={},
        execution_id=execution["id"],
        user_id="user-a",
    )

    updated = storage.get_execution(execution_id=execution["id"], task_id=task["id"])
    assert result["ok"] is True
    assert result["skipped"] is True
    assert updated["status"] == "cancelled"
    assert "task status is disabled" in updated["summary"]
