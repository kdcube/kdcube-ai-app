from __future__ import annotations

from kdcube_ai_app.apps.chat.sdk.solutions.tasks.storage import TaskStorage


def test_task_storage_default_list_excludes_archived_and_deleted(tmp_path):
    storage = TaskStorage(tmp_path, user_id="user-a")
    enabled = storage.create_task(title="Enabled task")
    disabled = storage.create_task(title="Disabled task")
    archived = storage.create_task(title="Archived task")
    deleted = storage.create_task(title="Deleted task")

    storage.set_task_status(task_id=disabled["id"], status="disabled")
    storage.set_task_status(task_id=archived["id"], status="archived")
    storage.set_task_status(task_id=deleted["id"], status="deleted")

    default_ids = {task["id"] for task in storage.list_tasks()}

    assert enabled["id"] in default_ids
    assert disabled["id"] in default_ids
    assert archived["id"] not in default_ids
    assert deleted["id"] not in default_ids
    assert storage.list_tasks(status="deleted")[0]["id"] == deleted["id"]
