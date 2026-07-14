# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""The multimodality seam — materialize hosted attachments + thread them in.

Offline tests (no store, no network):

  1. ``materialize_turn_attachments`` turns a hosted image attachment that already
     carries a base64 body into a native image block; skips unsupported mimes; and
     returns ``[]`` for a text-only turn.
  2. ``to_human_message_content`` keeps text-only as a PLAIN STRING (no behavior
     change) and builds a ``[text, blocks...]`` list only when attachments exist.
  3. Both input builders shape the current user turn correctly: text-only stays a
     plain ``("user", text)`` (lg-react) / text field (lg-solution), and with
     attachments becomes a multimodal ``HumanMessage`` (lg-react) / rides the
     ``attachments`` slot (lg-solution).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import HumanMessage

from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]

_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


def _attachments_module():
    _n, m = load_dynamic_module_for_path(BUNDLE_ROOT / "platform" / "attachments.py")
    return m


def _entrypoint_module():
    _n, m = load_dynamic_module_for_path(BUNDLE_ROOT / "entrypoint.py")
    return m


def _attachment_event(*, mime: str, base64_body: str | None, hosted_uri: str = "conv:fi:x") -> dict:
    body = {"mime": mime, "hosted_uri": hosted_uri}
    if base64_body is not None:
        body["base64"] = base64_body
    return {
        "type": "event.user.attachment.image",
        "payload": {"event": body},
    }


# ── 1. materialization ───────────────────────────────────────────────────────

def test_base64_image_attachment_becomes_an_image_block() -> None:
    mod = _attachments_module()
    events = [
        {"type": "chat.message", "text": "what is this?"},
        _attachment_event(mime="image/png", base64_body=_PNG_B64),
    ]
    blocks = asyncio.run(mod.materialize_turn_attachments(events))
    assert len(blocks) == 1
    blk = blocks[0]
    assert blk["type"] == "image"
    assert blk["media_type"] == "image/png"
    assert blk["data"]  # non-empty base64 (normalized image kept intact / downscaled)


def test_unsupported_mime_is_skipped_cleanly() -> None:
    mod = _attachments_module()
    events = [_attachment_event(mime="application/zip", base64_body=_PNG_B64)]
    assert asyncio.run(mod.materialize_turn_attachments(events)) == []


def test_no_attachments_returns_empty() -> None:
    mod = _attachments_module()
    events = [{"type": "chat.message", "text": "hello"}]
    assert asyncio.run(mod.materialize_turn_attachments(events)) == []
    assert asyncio.run(mod.materialize_turn_attachments([])) == []


def test_attachment_without_bytes_or_store_is_skipped() -> None:
    # No base64 body and no reachable store (offline) -> the attachment is skipped,
    # never fatal.
    mod = _attachments_module()
    events = [_attachment_event(mime="image/png", base64_body=None)]
    # Force the store-open to fail so we exercise the skip path deterministically.
    mod._open_conversation_store = lambda: None  # type: ignore[attr-defined]
    assert asyncio.run(mod.materialize_turn_attachments(events)) == []


# ── 2. content shaping ───────────────────────────────────────────────────────

def test_to_human_message_content_text_only_is_a_plain_string() -> None:
    mod = _attachments_module()
    assert mod.to_human_message_content("hi", []) == "hi"


def test_to_human_message_content_with_attachments_is_a_block_list() -> None:
    mod = _attachments_module()
    blocks = [{"type": "image", "data": _PNG_B64, "media_type": "image/png"}]
    content = mod.to_human_message_content("hi", blocks)
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "hi"}
    assert content[1]["type"] == "image"


# ── 3. input builders ────────────────────────────────────────────────────────

def _ident():
    return SimpleNamespace(user_id="t:p:lg:alice", thread_id="t:p:lg:alice:c1")


def test_prebuilt_inputs_text_only_stays_a_plain_tuple() -> None:
    ep = _entrypoint_module()
    inputs, _cfg = ep._prebuilt_inputs("hello", _ident(), [])
    assert inputs["messages"] == [("user", "hello")]


def test_prebuilt_inputs_with_attachments_is_a_multimodal_human_message() -> None:
    ep = _entrypoint_module()
    blocks = [{"type": "image", "data": _PNG_B64, "media_type": "image/png"}]
    inputs, _cfg = ep._prebuilt_inputs("what is this?", _ident(), blocks)
    msg = inputs["messages"][0]
    assert isinstance(msg, HumanMessage)
    assert isinstance(msg.content, list)
    assert msg.content[0] == {"type": "text", "text": "what is this?"}
    assert msg.content[1]["type"] == "image"


def test_solution_inputs_threads_attachments_on_a_separate_slot() -> None:
    ep = _entrypoint_module()
    blocks = [{"type": "image", "data": _PNG_B64, "media_type": "image/png"}]
    inputs, _cfg = ep._solution_inputs("what is this?", _ident(), blocks)
    # The text history stays plain (no base64 bloat in the checkpointed messages);
    # the multimodal blocks ride the `attachments` slot for the answer node.
    assert inputs["messages"] == [("user", "what is this?")]
    assert inputs["attachments"] == blocks
    assert inputs["question"] == "what is this?"


def test_solution_inputs_text_only_has_empty_attachments() -> None:
    ep = _entrypoint_module()
    inputs, _cfg = ep._solution_inputs("hello", _ident(), [])
    assert inputs["attachments"] == []
    assert inputs["messages"] == [("user", "hello")]
