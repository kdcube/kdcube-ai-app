# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from kdcube_ai_app.apps.chat.sdk.solutions.react.layout import (
    build_assistant_completion_blocks,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.proto import RuntimeCtx


def _block_factory(**kwargs):
    return dict(kwargs)


def test_build_assistant_completion_blocks_numbers_earlier_entries_and_keeps_latest_alias():
    runtime = RuntimeCtx(turn_id="turn_1", started_at="2026-04-26T10:00:00Z")

    blocks = build_assistant_completion_blocks(
        runtime=runtime,
        completion_entries=[
            {"text": "First answer", "ts": "2026-04-26T10:01:00Z"},
            {"text": "Second answer", "ts": "2026-04-26T10:02:00Z"},
            {"text": "Final answer", "ts": "2026-04-26T10:03:00Z"},
        ],
        final_answer_text="Final answer",
        ended_at="2026-04-26T10:03:00Z",
        block_factory=_block_factory,
    )

    assert [b["path"] for b in blocks] == [
        "ar:turn_1.assistant.completion.1",
        "ar:turn_1.assistant.completion.2",
        "ar:turn_1.assistant.completion",
    ]
    assert blocks[-1]["text"] == "Final answer"
    assert blocks[-1]["meta"]["completion_index"] == 3
    assert blocks[-1]["meta"]["completion_count"] == 3


def test_build_assistant_completion_blocks_appends_settled_answer_when_latest_attempt_differs():
    runtime = RuntimeCtx(turn_id="turn_2", started_at="2026-04-26T10:00:00Z")

    blocks = build_assistant_completion_blocks(
        runtime=runtime,
        completion_entries=[
            {"text": "Visible draft", "ts": "2026-04-26T10:01:00Z", "iteration": 4},
        ],
        final_answer_text="Settled answer",
        ended_at="2026-04-26T10:02:00Z",
        block_factory=_block_factory,
    )

    assert [b["text"] for b in blocks] == ["Visible draft", "Settled answer"]
    assert [b["path"] for b in blocks] == [
        "ar:turn_2.assistant.completion.1",
        "ar:turn_2.assistant.completion",
    ]


def test_build_assistant_completion_blocks_keeps_latest_alias_at_first_visible_timestamp_when_text_matches_last_attempt():
    runtime = RuntimeCtx(turn_id="turn_3", started_at="2026-04-26T10:00:00Z")

    blocks = build_assistant_completion_blocks(
        runtime=runtime,
        completion_entries=[
            {"text": "Same final answer", "ts": "2026-04-26T10:01:00Z"},
        ],
        final_answer_text="Same final answer",
        ended_at="2026-04-26T10:05:00Z",
        block_factory=_block_factory,
    )

    assert len(blocks) == 1
    assert blocks[0]["path"] == "ar:turn_3.assistant.completion"
    assert blocks[0]["ts"] == "2026-04-26T10:01:00Z"
