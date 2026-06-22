from __future__ import annotations

import json

from kdcube_ai_app.apps.chat.sdk.runtime.workspace import artifact_outdir_for
from kdcube_ai_app.apps.chat.sdk.solutions.canvas.events.policies import canvas_read_block_policy
from kdcube_ai_app.apps.chat.sdk.solutions.canvas.events.resolver import CanvasArtifactResolver
from kdcube_ai_app.apps.chat.sdk.solutions.react.proto import RuntimeCtx


class _FakeArtifacts:
    def read(self, key: str) -> bytes:
        assert key == "canvas/users/user-1/files/report.html"
        return b"<html>Hello</html>"


class _FakeStore:
    tenant = "tenant"
    project = "project"
    bundle_id = "bundle@1"
    artifact_resolver_name = "canvas.bundle_artifact_storage"
    artifacts = _FakeArtifacts()


def test_canvas_artifact_download_returns_url_not_json_bytes():
    resolver = CanvasArtifactResolver(_FakeStore())  # type: ignore[arg-type]

    result = resolver.download_ref("cnv:canvas/users/user-1/files/report.html", mime="text/html")

    assert result["ok"] is True
    assert result["filename"] == "report.html"
    assert result["mime"] == "text/html"
    assert result["size"] == len(b"<html>Hello</html>")
    assert "content_base64" not in result
    assert result["download_url"].startswith(
        "/api/integrations/bundles/tenant/project/bundle%401/operations/canvas_object_download?"
    )
    assert "object_ref=cnv%3Acanvas%2Fusers%2Fuser-1%2Ffiles%2Freport.html" in result["download_url"]


def test_canvas_read_stats_policy_emits_original_object_stats_on_block(tmp_path):
    runtime = RuntimeCtx(turn_id="turn_read", outdir=str(tmp_path), workdir=str(tmp_path))
    physical_path = "turn_read/snapshots/cnv/main.json"
    target_path = artifact_outdir_for(tmp_path) / physical_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps({
            "ok": True,
            "canvas_name": "main",
            "canvas_id": "cnv:user-1:main",
            "revision": 7,
            "canvas_ref": "cnv:main@7",
            "latest_ref": "cnv:main",
            "projection": {
                "canvas_name": "main",
                "canvas_id": "cnv:user-1:main",
                "revision": 7,
                "cards_count": 2,
                "placed_count": 1,
                "floating_count": 1,
                "legend": [{"id": "card-1", "selected": True}],
            },
        }),
        encoding="utf-8",
    )
    target = {
        "stats_only": True,
        "turn_id": "turn_read",
        "tool_call_id": "read_1",
        "tool_id": "canvas.read",
        "event_source_id": "canvas.read",
        "object_ref": "cnv:main",
        "logical_path": "fi:turn_read.snapshots/cnv/main.json",
        "path": "fi:turn_read.snapshots/cnv/main.json",
        "physical_path": physical_path,
        "blocks": [],
    }

    canvas_read_block_policy(target, runtime_ctx=runtime)

    assert target["blocks"]
    stats = target["blocks"][0]["original_object_stats"]
    assert stats["kind"] == "canvas_snapshot"
    assert stats["object_ref"] == "cnv:main"
    assert stats["live_ref"] == "cnv:main"
    assert stats["revision_ref"] == "cnv:main@7"
    assert stats["cards_count"] == 2
    assert stats["selected_card_ids"] == ["card-1"]
