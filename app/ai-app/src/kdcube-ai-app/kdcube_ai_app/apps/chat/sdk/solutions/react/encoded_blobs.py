# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Keep encoded binary payloads out of the model-visible context.

The context protocol is handles-over-bytes: files live in the artifact
workspace / object storage and the model works with their refs and paths,
while tools read the bytes themselves. A long base64 run inside timeline
text (a tool result echoing an encoded file, a text-file preview of an
encoded artifact, a prior model message restating a blob) burns tokens and
teaches the model to keep round-tripping bytes through text.

This module detects such runs and replaces them with a short instructive
marker that names the ref-based way to move the file. It is applied at the
two context choke points:

- block contribution (``react.tools.common.add_block``) — tool call/result
  blocks are scrubbed before they are stored on the timeline;
- timeline rendering (``timeline._blocks_to_message_blocks``) — every block
  text is scrubbed again on its way into the model prompt, which also covers
  blocks that entered storage by other paths (thinking, completions,
  restored history).

Only plain text is inspected. Structured ``base64`` fields that feed
multimodal image/document parts are separate block fields and stay intact.
"""

from __future__ import annotations

import re

# A run of base64 alphabet at least this long is treated as an encoded blob.
# Real prose, ids, and hashes stay far below it; a data-URI icon is a few
# hundred chars; encoded files (the case this guards) run into thousands.
ENCODED_BLOB_MIN_CHARS = 2048

# One unbroken base64 run (also matches the payload tail of data: URIs).
_BASE64_RUN_RE = re.compile(r"[A-Za-z0-9+/]{%d,}={0,2}" % ENCODED_BLOB_MIN_CHARS)

# MIME-style wrapped base64: consecutive full lines of base64 alphabet.
_BASE64_LINE_RE = re.compile(r"^[A-Za-z0-9+/]{60,}={0,2}$")


def encoded_blob_marker(chars: int) -> str:
    approx_kb = max(1, round((chars * 3 / 4) / 1024))
    return (
        f"[ENCODED FILE CONTENT ELIDED: {chars} base64 chars (~{approx_kb} KB). "
        "Bytes live in the file/artifact storage; the context carries its ref. "
        "Pass the file by its path/ref (e.g. the react.pull result's logical_path/"
        "physical_path in a file-accepting field such as attachment_paths or "
        "file_ref) — the receiving tool reads the bytes itself.]"
    )


def _elide_wrapped_lines(text: str) -> tuple[str, int]:
    """Collapse consecutive base64-looking lines whose total passes the threshold."""
    if "\n" not in text:
        return text, 0
    lines = text.split("\n")
    out: list[str] = []
    elided = 0
    i = 0
    while i < len(lines):
        j = i
        run_chars = 0
        while j < len(lines) and _BASE64_LINE_RE.match(lines[j].strip()):
            run_chars += len(lines[j].strip())
            j += 1
        if run_chars >= ENCODED_BLOB_MIN_CHARS:
            out.append(encoded_blob_marker(run_chars))
            elided += run_chars
            i = j
            continue
        out.append(lines[i])
        i += 1
    if not elided:
        return text, 0
    return "\n".join(out), elided


def elide_encoded_blobs(text: str) -> tuple[str, int]:
    """Replace large base64 runs in ``text`` with an instructive marker.

    Returns ``(scrubbed_text, elided_chars)``; ``elided_chars == 0`` means the
    text came back unchanged (the common case, checked cheaply).
    """
    raw = text if isinstance(text, str) else ""
    if len(raw) < ENCODED_BLOB_MIN_CHARS:
        return raw, 0

    elided = 0

    def _sub(match: re.Match[str]) -> str:
        nonlocal elided
        chars = len(match.group(0))
        elided += chars
        return encoded_blob_marker(chars)

    scrubbed = _BASE64_RUN_RE.sub(_sub, raw)
    scrubbed, wrapped = _elide_wrapped_lines(scrubbed)
    return (scrubbed, elided + wrapped) if (elided or wrapped) else (raw, 0)


def scrub_block_text(block: dict) -> dict:
    """Return ``block`` with large encoded blobs elided from its ``text``.

    The input mapping is never mutated; an unchanged block is returned as-is.
    """
    text = block.get("text")
    if not isinstance(text, str) or len(text) < ENCODED_BLOB_MIN_CHARS:
        return block
    scrubbed, elided = elide_encoded_blobs(text)
    if not elided:
        return block
    out = dict(block)
    out["text"] = scrubbed
    return out


__all__ = [
    "ENCODED_BLOB_MIN_CHARS",
    "elide_encoded_blobs",
    "encoded_blob_marker",
    "scrub_block_text",
]
