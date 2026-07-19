# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""send_to_user: files and links reach the user out-of-band of the model.

The regression this guards: a Slack file's signed download URL rode the tool
result into the model's context, the model re-typed it into chat, and one
flipped base64 character broke the HMAC. Delivery ships the OBJECT REF as a
chat.files event and strips the URL from the model-visible result."""

from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.widgets.send_to_user import (
    DELIVERED_NOTE,
    collect_file_deliveries,
    deliver_result_files,
    send_files_to_user,
    send_links_to_user,
)

SLACK_REF = "slack:slack_23e58d628df51576:file:F0BJ3DVTA85"


def _slack_url_result() -> dict:
    """The shape the slack named service returns on a turn-less transport."""
    return {
        "ok": True,
        "object_ref": SLACK_REF,
        "object": {
            "ref": SLACK_REF,
            "object_ref": SLACK_REF,
            "object_kind": "slack.file",
            "id": "F0BJ3DVTA85",
            "file_id": "F0BJ3DVTA85",
            "account_id": "slack_23e58d628df51576",
            "name": "IMG_4941 2.PNG",
            "mimetype": "image/png",
            "size": 75,
            "download": {
                "encoding": "url",
                "url": "http://example.test/integration_file_download?object_ref=x&download_token=SIGNED",
                "expires_at": 1784427951,
            },
        },
        "delivery": "url",
    }


class _FakeComm:
    def __init__(self):
        self.events = []

    async def event(self, **kwargs):
        self.events.append(kwargs)


def test_collect_strips_the_url_and_yields_the_object_ref_item():
    payload = _slack_url_result()
    rewritten, items = collect_file_deliveries(payload)

    assert len(items) == 1
    item = items[0]
    assert item["object_ref"] == SLACK_REF and item["ref"] == SLACK_REF
    assert item["filename"] == "IMG_4941 2.PNG"
    assert item["mime"] == "image/png"
    assert item["size"] == 75

    download = rewritten["object"]["download"]
    assert download == {"encoding": "chat", "delivered": True, "note": DELIVERED_NOTE}
    assert "download_token" not in str(rewritten)  # the signed URL is gone from the model view
    # The original payload object is untouched (rewrite is a copy).
    assert payload["object"]["download"]["encoding"] == "url"


def test_collect_leaves_urlless_payloads_alone():
    payload = {"ok": True, "object": {"ref": SLACK_REF, "download": {"encoding": "base64", "data": "x"}}}
    rewritten, items = collect_file_deliveries(payload)
    assert items == [] and rewritten is payload


@pytest.mark.asyncio
async def test_deliver_emits_chat_files_and_returns_model_safe_payload():
    comm = _FakeComm()
    result = await deliver_result_files(_slack_url_result(), comm=comm)

    assert len(comm.events) == 1
    event = comm.events[0]
    assert event["type"] == "chat.files" and event["step"] == "files"
    assert event["status"] == "completed"
    rows = event["data"]["items"]
    assert rows[0]["object_ref"] == SLACK_REF and rows[0]["filename"] == "IMG_4941 2.PNG"
    assert "download_token" not in str(rows)  # the event carries the ref, never the URL

    assert result["object"]["download"]["delivered"] is True
    assert "download_token" not in str(result)


@pytest.mark.asyncio
async def test_no_chat_lane_keeps_the_url_contract(monkeypatch):
    """Turn-less transports (external MCP clients) keep the URL in the result."""
    from kdcube_ai_app.apps.chat.sdk.runtime import comm_ctx

    monkeypatch.setattr(comm_ctx, "get_comm", lambda: None)
    payload = _slack_url_result()
    result = await deliver_result_files(payload)
    assert result is payload
    assert result["object"]["download"]["encoding"] == "url"


@pytest.mark.asyncio
async def test_send_links_placement_chat_marks_items():
    comm = _FakeComm()
    ok = await send_links_to_user(
        [{"url": "https://example.test/doc", "title": "Doc"}],
        placement="chat",
        comm=comm,
    )
    assert ok is True
    event = comm.events[0]
    assert event["type"] == "chat.citations" and event["step"] == "citations"
    assert event["data"]["items"][0]["placement"] == "chat"


@pytest.mark.asyncio
async def test_send_files_requires_items_and_comm():
    assert await send_files_to_user([], comm=_FakeComm()) is False
    assert await send_files_to_user([{"object_ref": "x", "ref": "x", "filename": "f"}], comm=object()) is False
