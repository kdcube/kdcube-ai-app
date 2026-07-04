from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.chat.events.resolver import (
    resolve_conversation_ref_action,
)


async def _fetch_details(_user_id: str, _conversation_id: str, _bundle_id: str | None):
    return None


@pytest.mark.asyncio
async def test_conv_fi_download_returns_resource_url_not_inline_base64():
    result = await resolve_conversation_ref_action(
        {
            "action": "download",
            "object_ref": (
                "conv:fi:conv_22643ddb-6c99-4055-a886-b69e62832f76."
                "turn_2026-07-04-13-18-11-048.files/expense_tracker/README.md"
            ),
            "filename": "README.md",
            "mime": "text/markdown",
        },
        user_id="02e53484-0081-70ce-11c1-e96706b1a182",
        tenant="demo-tenant",
        project="demo-project",
        fetch_details=_fetch_details,
    )

    assert result["ok"] is True
    assert result["object_kind"] == "conversation.file"
    assert result["filename"] == "README.md"
    assert result["mime"] == "text/markdown"
    assert "content_base64" not in result
    assert result["download_url"] == (
        "/api/cb/resources/demo-tenant/demo-project"
        "/conv/02e53484-0081-70ce-11c1-e96706b1a182/22643ddb-6c99-4055-a886-b69e62832f76"
        "/turn/turn_2026-07-04-13-18-11-048/attachment/"
        "turn_2026-07-04-13-18-11-048/files/expense_tracker/README.md/download"
    )


@pytest.mark.asyncio
async def test_conv_conversation_capabilities_stay_non_downloadable():
    result = await resolve_conversation_ref_action(
        {"action": "capabilities", "object_ref": "conv:conversation:c1"},
        user_id="u1",
        tenant="demo-tenant",
        project="demo-project",
        fetch_details=_fetch_details,
    )

    assert result["object_kind"] == "chat.conversation"
    assert result["capabilities"]["download"] is False
