# SPDX-License-Identifier: MIT

from __future__ import annotations

from kdcube_ai_app.apps.chat.sdk.solutions.react.workspace import extract_code_file_paths


def test_extract_code_file_paths_is_artifact_segment_aware():
    code = (
        'current = "turn_13083704/outputs/email-attachments/acct/msg/invoice.pdf"\n'
        'relative = "outputs/email-attachments/acct/msg/receipt.pdf"\n'
        'user_file = "attachments/uploaded.pdf"\n'
        'url = "https://example.com/attachments/not-local.pdf"\n'
    )

    paths, rewritten = extract_code_file_paths(code, turn_id="turn_13083704")

    assert paths == []
    assert rewritten == [
        "turn_13083704/outputs/email-attachments/acct/msg/receipt.pdf",
        "turn_13083704/attachments/uploaded.pdf",
    ]
    assert "turn_13083704/attachments/acct/msg/invoice.pdf" not in rewritten
    assert "turn_13083704/attachments/not-local.pdf" not in rewritten


def test_extract_code_file_paths_preserves_timestamp_turn_prefix():
    turn_id = "turn_2026-05-19-01-01-49-177"
    code = (
        f'out_path = Path(OUTPUT_DIR) / "{turn_id}/outputs/science_news/top3.xlsx"\n'
        'old_path = "turn_2026-05-18-01-01-49-177/files/input.csv"\n'
    )

    paths, rewritten = extract_code_file_paths(code, turn_id=turn_id)

    assert rewritten == []
    assert paths == ["turn_2026-05-18-01-01-49-177/files/input.csv"]
