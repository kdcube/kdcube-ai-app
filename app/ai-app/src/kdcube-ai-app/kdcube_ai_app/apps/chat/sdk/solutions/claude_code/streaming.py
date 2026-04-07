# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

from __future__ import annotations

from typing import Any


def extract_text_from_claude_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(part for part in (extract_text_from_claude_content(item) for item in value) if part)
    if not isinstance(value, dict):
        return ""

    if isinstance(value.get("text"), str):
        return value["text"]

    for key in ("content", "message", "delta", "result"):
        if key in value:
            text = extract_text_from_claude_content(value[key])
            if text:
                return text
    return ""


def extract_text_from_claude_event(value: Any) -> str:
    if not isinstance(value, dict):
        return ""

    for key in ("text", "completion", "message", "delta", "result", "content"):
        if key in value:
            text = extract_text_from_claude_content(value[key])
            if text:
                return text
    return ""


def compute_incremental_chunk(previous_snapshot: str, new_text: str) -> tuple[str, str]:
    if not new_text:
        return previous_snapshot, ""
    if not previous_snapshot:
        return new_text, new_text
    if new_text.startswith(previous_snapshot):
        return new_text, new_text[len(previous_snapshot):]

    common_prefix = 0
    for prev_char, next_char in zip(previous_snapshot, new_text):
        if prev_char != next_char:
            break
        common_prefix += 1
    return new_text, new_text[common_prefix:]
