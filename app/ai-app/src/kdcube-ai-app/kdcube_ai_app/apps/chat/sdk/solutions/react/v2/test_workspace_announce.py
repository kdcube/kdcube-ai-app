# SPDX-License-Identifier: MIT

import json
import pathlib
import subprocess

from kdcube_ai_app.apps.chat.sdk.solutions.react.v2.layout import build_announce_text
from kdcube_ai_app.apps.chat.sdk.solutions.react.v2.proto import RuntimeCtx


def test_build_announce_text_includes_git_workspace_summary(tmp_path):
    outdir = tmp_path / "out"
    turn_root = outdir / "turn_123"
    (turn_root / "files" / "projectA" / "src").mkdir(parents=True, exist_ok=True)
    (turn_root / "files" / "projectA" / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (outdir / "turn_122" / "files").mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "init", str(turn_root)], check=True, capture_output=True)

    runtime = RuntimeCtx(
        turn_id="turn_123",
        outdir=str(outdir),
        workspace_implementation="git",
    )

    publish_block = {
        "type": "react.workspace.publish",
        "turn_id": "turn_122",
        "path": "ar:turn_122.react.workspace.publish",
        "mime": "application/json",
        "text": json.dumps({
            "turn_id": "turn_122",
            "status": "succeeded",
        }),
    }

    announce_text = build_announce_text(
        iteration=1,
        max_iterations=6,
        started_at="2026-04-02T10:00:00Z",
        timezone="UTC",
        runtime_ctx=runtime,
        timeline_blocks=[publish_block],
        constraints=None,
        feedback_updates=None,
        feedback_incorporated=False,
        mode="full",
    )

    assert "[WORKSPACE]" in announce_text
    assert "implementation: git" in announce_text
    assert "current_turn_root: turn_123/" in announce_text
    assert "materialized_turn_roots: turn_122, turn_123 (current)" in announce_text
    assert "current_turn_scopes:" in announce_text
    assert "- projectA/ (1 file)" in announce_text
    assert "repo_mode: sparse git repo" in announce_text
    assert "repo_status: dirty" in announce_text
    assert "current_turn_publish: pending" in announce_text
    assert "last_published_turn: turn_122 (succeeded)" in announce_text
