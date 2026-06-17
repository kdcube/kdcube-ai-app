from __future__ import annotations

import re

from kdcube_ai_app.apps.chat.sdk.context.memory.store import _new_memory_id


def test_new_memory_ids_are_timestamp_based() -> None:
    memory_id = _new_memory_id()

    assert re.fullmatch(r"mem_\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-\d{9}", memory_id)
