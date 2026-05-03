# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.sdk.storage.conversation_store import ConversationStore


@pytest.mark.asyncio
async def test_file_attachment_uri_is_absolute_file_uri(tmp_path):
    store = ConversationStore(storage_uri=tmp_path.as_uri())

    uri, key, _rn = await store.put_attachment(
        tenant="tenant",
        project="project",
        user="user",
        fingerprint=None,
        conversation_id="conversation",
        turn_id="turn_1",
        filename="report.xlsx",
        data=b"xlsx-bytes",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    assert uri.startswith("file:///")
    assert "file://tmp" not in uri
    assert key == "cb/tenants/tenant/projects/project/attachments/user/conversation/turn_1/report.xlsx"
    assert await store.get_blob_bytes(uri) == b"xlsx-bytes"
