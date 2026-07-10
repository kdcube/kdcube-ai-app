# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Encoded blobs stay out of the model context: handles in context, bytes in storage."""

import base64
import re

from kdcube_ai_app.apps.chat.sdk.solutions.react.encoded_blobs import (
    ENCODED_BLOB_MIN_CHARS,
    elide_encoded_blobs,
    encoded_blob_marker,
    scrub_block_text,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.tools.common import add_block
from kdcube_ai_app.apps.chat.sdk.solutions.react.timeline import (
    _scrub_encoded_blobs_in_message_blocks,
)


def _blob(size_bytes: int = 6000) -> str:
    return base64.b64encode(b"\x89SVG-binary-payload" * (size_bytes // 16)).decode("ascii")


def _has_long_base64_run(text: str, min_len: int = 512) -> bool:
    return re.search(r"[A-Za-z0-9+/]{%d,}" % min_len, text) is not None


class _RuntimeCtx:
    turn_id = "turn_test"


class _Ctx:
    runtime_ctx = _RuntimeCtx()

    def __init__(self):
        self.blocks = []

    def contribute(self, *, blocks):
        self.blocks.extend(blocks)


def test_single_base64_run_is_elided_with_instructive_marker():
    blob = _blob()
    text = f"payload:\n{blob}\ndone"

    scrubbed, elided = elide_encoded_blobs(text)

    assert elided == len(blob)
    assert not _has_long_base64_run(scrubbed)
    assert "ENCODED FILE CONTENT ELIDED" in scrubbed
    # The marker names the fix: pass the file by path/ref.
    assert "attachment_paths" in scrubbed
    assert "logical_path" in scrubbed
    assert scrubbed.startswith("payload:")
    assert scrubbed.endswith("done")


def test_mime_wrapped_base64_lines_are_elided():
    blob = _blob(6000)
    wrapped = "\n".join(blob[i:i + 76] for i in range(0, len(blob), 76))
    text = f"BEGIN\n{wrapped}\nEND"

    scrubbed, elided = elide_encoded_blobs(text)

    assert elided >= ENCODED_BLOB_MIN_CHARS
    assert not _has_long_base64_run(scrubbed, min_len=76)
    assert "ENCODED FILE CONTENT ELIDED" in scrubbed
    assert scrubbed.splitlines()[0] == "BEGIN"
    assert scrubbed.splitlines()[-1] == "END"


def test_ordinary_text_and_small_data_uris_pass_through():
    small_icon = base64.b64encode(b"tiny-icon-bytes" * 20).decode("ascii")
    text = "prose with ids like tc_41491d2c14a4 and a small data:image/png;base64," + small_icon

    scrubbed, elided = elide_encoded_blobs(text)

    assert elided == 0
    assert scrubbed == text


def test_marker_reports_approximate_size():
    marker = encoded_blob_marker(7632)
    assert "7632 base64 chars" in marker
    assert "KB" in marker


def test_scrub_block_text_returns_same_block_when_clean():
    block = {"type": "react.tool.result", "text": "short"}
    assert scrub_block_text(block) is block


def test_add_block_refifies_base64_in_tool_result_text():
    ctx = _Ctx()
    blob = _blob()
    add_block(ctx, {
        "turn": "turn_test",
        "type": "react.tool.result",
        "mime": "application/json",
        "text": f'{{"payload": "{blob}"}}',
    })

    assert len(ctx.blocks) == 1
    stored = ctx.blocks[0]["text"]
    assert not _has_long_base64_run(stored)
    assert "ENCODED FILE CONTENT ELIDED" in stored


def test_regression_base64_encoded_file_preview_never_reaches_context():
    """Surfaced case: the model exec-encoded a pulled SVG into
    email_attachment_b64.txt; the produced-file TEXT FILE PREVIEW echoed the
    full 7632-char base64 blob into the visible timeline. The stored block
    must carry the ref-ified note and zero base64."""
    ctx = _Ctx()
    svg_b64 = base64.b64encode(b"<svg>" + b"x" * 5724 + b"</svg>").decode("ascii")
    preview = "\n".join([
        "[TEXT FILE PREVIEW]",
        "path: turn_2026-07-10-07-02-47-073/files/email_attachment_b64.txt",
        "lines: [1-1]/1",
        "",
        f"     1\t{svg_b64}",
    ])
    add_block(ctx, {
        "turn": "turn_2026-07-10-07-02-47-073",
        "type": "react.tool.result",
        "mime": "text/plain",
        "path": "conv:tc:turn_2026-07-10-07-02-47-073.tc_41491d2c14a4.artifact",
        "text": preview,
    })

    stored = ctx.blocks[0]["text"]
    assert "email_attachment_b64.txt" in stored  # the handle stays
    assert not _has_long_base64_run(stored)
    assert "ENCODED FILE CONTENT ELIDED" in stored


def test_render_side_scrub_covers_text_parts_and_keeps_binary_parts():
    blob = _blob()
    text_part = {"type": "text", "text": f"[thinking]\nThe base64 content is:\n{blob}", "cache": True}
    image_part = {"type": "image", "source": {"data": blob, "media_type": "image/png"}}

    out = _scrub_encoded_blobs_in_message_blocks([text_part, image_part])

    assert out[0]["cache"] is True
    assert not _has_long_base64_run(out[0]["text"])
    assert "ENCODED FILE CONTENT ELIDED" in out[0]["text"]
    # multimodal payloads ride outside "text" and stay intact
    assert out[1]["source"]["data"] == blob


def test_render_side_scrub_is_deterministic_for_cache_stability():
    blob = _blob()
    once = _scrub_encoded_blobs_in_message_blocks([{"type": "text", "text": f"a {blob} b"}])[0]["text"]
    twice = _scrub_encoded_blobs_in_message_blocks([{"type": "text", "text": f"a {blob} b"}])[0]["text"]
    assert once == twice
