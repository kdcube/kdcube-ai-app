# SPDX-License-Identifier: MIT

from __future__ import annotations

import base64

import pytest

from kdcube_ai_app.apps.chat.sdk.runtime.user_inputs import ingest_user_attachments


@pytest.mark.asyncio
async def test_ingest_user_attachments_extracts_base64_text_attachment():
    result = await ingest_user_attachments(
        attachments=[
            {
                "filename": "note.txt",
                "mime": "text/plain",
                "base64": base64.b64encode(b"hello from telegram").decode("ascii"),
            }
        ],
        store=None,
    )

    assert len(result) == 1
    assert result[0]["filename"] == "note.txt"
    assert result[0]["mime"] == "text/plain"
    assert result[0]["text"] == "hello from telegram"
    assert result[0]["base64"]


@pytest.mark.asyncio
async def test_ingest_user_attachments_reports_invalid_base64_attachment():
    result = await ingest_user_attachments(
        attachments=[
            {
                "filename": "broken.txt",
                "mime": "text/plain",
                "base64": "not-valid-base64",
            }
        ],
        store=None,
    )

    assert len(result) == 1
    assert result[0]["filename"] == "broken.txt"
    assert result[0]["error"].startswith("base64_decode_failed:")
