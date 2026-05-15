from kdcube_ai_app.apps.chat.sdk.solutions.react.compaction_memory import (
    build_internal_note_compaction_result,
)


def test_multiline_internal_note_is_preserved_as_authored_with_tags():
    result = build_internal_note_compaction_result(
        blocks=[
            {
                "type": "react.note",
                "path": "fi:turn_old.outputs/internal_notes/beacons.md",
                "text": "\n".join(
                    [
                        "[K] fi:turn_old.outputs/report.html - source for rendered PDF",
                        "[D] Renderer refs should point at source text artifacts.",
                        "[P] User prefers direct engineering explanations.",
                    ]
                ),
                "meta": {"channel": "internal"},
            }
        ],
        turn_id="turn_summary",
        summary_text="SUMMARY",
    )

    assert [b.get("text") for b in result.preserved_blocks] == [
        "\n".join(
            [
                "[K] fi:turn_old.outputs/report.html - source for rendered PDF",
                "[D] Renderer refs should point at source text artifacts.",
                "[P] User prefers direct engineering explanations.",
            ]
        )
    ]
    assert [b.get("path") for b in result.preserved_blocks] == [
        "ar:turn_summary.react.note.preserved.1",
    ]
    meta = result.preserved_blocks[0].get("meta") or {}
    assert meta.get("source_path") == "fi:turn_old.outputs/internal_notes/beacons.md"
    assert meta.get("note_tags") == ["K", "D", "P"]
    assert "[INTERNAL MEMORY DIGEST]" in result.summary_text
    assert "User prefers direct engineering explanations." in result.summary_text
    assert "Renderer refs should point" not in result.summary_text


def test_internal_note_cap_applies_across_note_blocks_not_tags():
    blocks = []
    tags = ["K", "D", "S", "A", "P", "K", "D", "S"]
    for idx, tag in enumerate(tags):
        blocks.append(
            {
                "type": "react.note",
                "path": f"fi:turn_old.outputs/internal_notes/note-{idx}.md",
                "text": f"[{tag}] note {idx}",
                "meta": {"channel": "internal"},
            }
        )
    result = build_internal_note_compaction_result(
        blocks=blocks,
        turn_id="turn_summary",
        summary_text="SUMMARY",
        max_promoted_notes=4,
    )

    assert [b.get("text") for b in result.preserved_blocks] == [
        "[P] note 4",
        "[K] note 5",
        "[D] note 6",
        "[S] note 7",
    ]
