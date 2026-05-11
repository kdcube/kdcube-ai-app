# SPDX-License-Identifier: MIT

import json

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.react.proto import RuntimeCtx
from kdcube_ai_app.apps.chat.sdk.solutions.react.v2.tools.patch import handle_react_patch
from kdcube_ai_app.apps.chat.sdk.solutions.react.v2.tools.tests.helpers import FakeBrowser, FakeReact
from kdcube_ai_app.apps.chat.sdk.runtime.workspace import artifact_outdir_for


class _FakeComm:
    def __init__(self):
        self.service = {
            "request_id": "req_1",
            "tenant": "tenant_1",
            "project": "project_1",
            "user": "user_1",
            "conversation_id": "conv_1",
            "user_type": "human",
        }
        self.user_id = "user_1"
        self.user_type = "human"


class _FakeHostingService:
    def __init__(self):
        self.calls = []
        self.emitted = []

    async def host_files_to_conversation(self, **kwargs):
        self.calls.append(kwargs)
        artifact = (kwargs.get("files") or [{}])[0]
        value = artifact.get("value") or {}
        return [{
            "hosted_uri": "hosted://artifact/a.txt",
            "rn": "rn:artifact:a.txt",
            "key": "artifact/a.txt",
            "physical_path": value.get("path") or "",
        }]

    async def emit_solver_artifacts(self, *, files, citations):
        self.emitted.append({"files": files, "citations": citations})


@pytest.mark.asyncio
async def test_patch_rejects_historical_path_without_copying(tmp_path):
    runtime = RuntimeCtx(turn_id="turn_new", outdir=str(tmp_path), workdir=str(tmp_path))
    ctx = FakeBrowser(runtime)

    old_path = tmp_path / "turn_old" / "files"
    old_path.mkdir(parents=True, exist_ok=True)
    (old_path / "a.txt").write_text("old", encoding="utf-8")

    state = {
        "last_decision": {"tool_call": {"params": {"path": "turn_old/files/a.txt", "patch": "new", "kind": "display"}}},
        "outdir": str(tmp_path),
    }

    await handle_react_patch(react=FakeReact(), ctx_browser=ctx, state=state, tool_call_id="p1")

    new_path = tmp_path / "turn_new" / "files" / "a.txt"
    assert not new_path.exists()
    assert (old_path / "a.txt").read_text(encoding="utf-8") == "old"
    json_blocks = [b for b in ctx.timeline.blocks if b.get("type") == "react.tool.result" and b.get("mime") == "application/json"]
    assert json_blocks
    payload = json.loads(json_blocks[-1]["text"])
    assert payload["ok"] is False
    assert payload["error"] == "patch_requires_current_turn_path"


@pytest.mark.asyncio
async def test_patch_applies_unified_diff_and_rewrites_headers(tmp_path):
    runtime = RuntimeCtx(turn_id="turn_new", outdir=str(tmp_path), workdir=str(tmp_path))
    ctx = FakeBrowser(runtime)

    target = tmp_path / "turn_new" / "files" / "a.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    patch_text = "\n".join([
        "--- a/a.txt",
        "+++ b/a.txt",
        "@@ -1,3 +1,4 @@",
        " alpha",
        "+inserted",
        " beta",
        " gamma",
        "",
    ])
    state = {
        "last_decision": {
            "tool_call": {
                "params": {
                    "path": "files/a.txt",
                    "channel": "canvas",
                    "patch": patch_text,
                    "kind": "display",
                }
            }
        },
        "outdir": str(tmp_path),
    }

    await handle_react_patch(react=FakeReact(), ctx_browser=ctx, state=state, tool_call_id="p2")

    assert target.read_text(encoding="utf-8") == "alpha\ninserted\nbeta\ngamma\n"

    result_blocks = [b for b in ctx.timeline.blocks if b.get("type") == "react.tool.result" and b.get("mime") == "text/markdown"]
    assert result_blocks
    rendered_patch = result_blocks[-1].get("text") or ""
    assert str(target) in rendered_patch


@pytest.mark.asyncio
async def test_patch_file_kind_hosts_and_emits_file(tmp_path):
    runtime = RuntimeCtx(turn_id="turn_new", outdir=str(tmp_path), workdir=str(tmp_path))
    ctx = FakeBrowser(runtime)
    hosting = _FakeHostingService()
    comm = _FakeComm()

    target = tmp_path / "turn_new" / "files" / "a.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old", encoding="utf-8")

    state = {
        "last_decision": {
            "tool_call": {
                "params": {
                    "path": "files/a.txt",
                    "channel": "canvas",
                    "patch": "new",
                    "kind": "file",
                }
            }
        },
        "outdir": str(tmp_path),
    }

    await handle_react_patch(
        react=FakeReact(hosting_service=hosting, comm=comm),
        ctx_browser=ctx,
        state=state,
        tool_call_id="p3",
    )

    assert hosting.calls
    hosted_artifact = hosting.calls[0]["files"][0]
    assert hosted_artifact["value"]["type"] == "file"
    assert hosted_artifact["value"]["path"] == "turn_new/files/a.txt"
    assert hosting.emitted

    json_blocks = [b for b in ctx.timeline.blocks if b.get("type") == "react.tool.result" and b.get("mime") == "application/json"]
    assert json_blocks
    payload = json.loads(json_blocks[-1]["text"])
    assert payload["ok"] is True


@pytest.mark.asyncio
async def test_patch_updates_existing_current_turn_file_without_react_write_registration(tmp_path):
    runtime = RuntimeCtx(turn_id="turn_new", outdir=str(tmp_path), workdir=str(tmp_path))
    ctx = FakeBrowser(runtime)

    target = tmp_path / "turn_new" / "files" / "demo" / "config.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        '"""Project configuration constants."""\n\n'
        'DATABASE_URL = "postgresql://localhost:5432/mydb"\n'
        "MAX_RETRIES = 5\n"
        'LOG_LEVEL = "INFO"\n',
        encoding="utf-8",
    )

    patch_text = "\n".join([
        "--- a/config.py",
        "+++ b/config.py",
        "@@ -1,5 +1,6 @@",
        ' """Project configuration constants."""',
        "",
        "+from utils import MAX_RETRIES",
        "+",
        ' DATABASE_URL = "postgresql://localhost:5432/mydb"',
        "-MAX_RETRIES = 5",
        ' LOG_LEVEL = "INFO"',
        "",
    ])
    state = {
        "last_decision": {
            "tool_call": {
                "params": {
                    "path": "files/demo/config.py",
                    "channel": "canvas",
                    "patch": patch_text,
                    "kind": "display",
                }
            }
        },
        "outdir": str(tmp_path),
    }

    await handle_react_patch(react=FakeReact(), ctx_browser=ctx, state=state, tool_call_id="p_current")

    assert target.read_text(encoding="utf-8") == (
        '"""Project configuration constants."""\n\n'
        "from utils import MAX_RETRIES\n\n"
        'DATABASE_URL = "postgresql://localhost:5432/mydb"\n'
        'LOG_LEVEL = "INFO"\n'
    )
    assert not any(
        b.get("type") == "react.tool.result" and '"ok": false' in (b.get("text") or "").lower()
        for b in ctx.timeline.blocks
    )


@pytest.mark.asyncio
async def test_patch_accepts_current_turn_file_in_split_artifact_root(tmp_path):
    runtime_outdir = tmp_path / "out"
    runtime = RuntimeCtx(turn_id="turn_new", outdir=str(runtime_outdir), workdir=str(tmp_path / "work"))
    ctx = FakeBrowser(runtime)
    artifact_outdir = artifact_outdir_for(runtime_outdir)
    target = artifact_outdir / "turn_new" / "files" / "demo" / "app.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old\n", encoding="utf-8")

    state = {
        "last_decision": {
            "tool_call": {
                "params": {
                    "path": "files/demo/app.py",
                    "channel": "canvas",
                    "patch": "new\n",
                    "kind": "display",
                }
            }
        },
        "outdir": str(runtime_outdir),
    }

    await handle_react_patch(react=FakeReact(), ctx_browser=ctx, state=state, tool_call_id="p_split")

    assert target.read_text(encoding="utf-8") == "new\n"


@pytest.mark.asyncio
async def test_patch_rejects_generic_outdir_fi_path(tmp_path):
    runtime = RuntimeCtx(turn_id="turn_new", outdir=str(tmp_path), workdir=str(tmp_path))
    ctx = FakeBrowser(runtime)

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    target = logs_dir / "docker.err.log"
    target.write_text("old", encoding="utf-8")

    state = {
        "last_decision": {
            "tool_call": {
                "params": {
                    "path": "fi:logs/docker.err.log",
                    "channel": "canvas",
                    "patch": "new",
                    "kind": "display",
                }
            }
        },
        "outdir": str(tmp_path),
    }

    await handle_react_patch(react=FakeReact(), ctx_browser=ctx, state=state, tool_call_id="p4")

    assert target.read_text(encoding="utf-8") == "old"
    json_blocks = [
        b for b in ctx.timeline.blocks
        if b.get("type") == "react.tool.result" and b.get("mime") == "application/json"
    ]
    assert json_blocks
    payload = json.loads(json_blocks[-1]["text"])
    assert payload["ok"] is False
    assert payload["error"] == "patch_requires_current_turn_path"


@pytest.mark.asyncio
async def test_patch_failure_emits_result_block(tmp_path):
    runtime = RuntimeCtx(turn_id="turn_new", outdir=str(tmp_path), workdir=str(tmp_path))
    ctx = FakeBrowser(runtime)

    state = {
        "last_decision": {
            "tool_call": {
                "params": {
                    "path": "turn_new/files/missing.txt",
                    "channel": "canvas",
                    "patch": "@@ -1 +1 @@\n-old\n+new\n",
                    "kind": "display",
                }
            }
        },
        "outdir": str(tmp_path),
    }

    out = await handle_react_patch(react=FakeReact(), ctx_browser=ctx, state=state, tool_call_id="p_fail")

    assert "exit_reason" not in out
    assert "error" not in out
    json_blocks = [
        b for b in ctx.timeline.blocks
        if b.get("type") == "react.tool.result" and b.get("mime") == "application/json"
    ]
    assert json_blocks
    payload = json.loads(json_blocks[-1]["text"])
    assert payload["ok"] is False
    assert payload["error"] == "patch_target_missing"


@pytest.mark.asyncio
async def test_patch_rejects_unmaterialized_historical_file(tmp_path):
    runtime = RuntimeCtx(turn_id="turn_new", outdir=str(tmp_path), workdir=str(tmp_path))
    ctx = FakeBrowser(runtime)

    state = {
        "last_decision": {
            "tool_call": {
                "params": {
                    "path": "turn_old/files/a.txt",
                    "channel": "canvas",
                    "patch": "new",
                    "kind": "display",
                }
            }
        },
        "outdir": str(tmp_path),
    }

    out = await handle_react_patch(react=FakeReact(), ctx_browser=ctx, state=state, tool_call_id="p_pull")

    assert "exit_reason" not in out
    assert "error" not in out
    json_blocks = [
        b for b in ctx.timeline.blocks
        if b.get("type") == "react.tool.result" and b.get("mime") == "application/json"
    ]
    assert json_blocks
    payload = json.loads(json_blocks[-1]["text"])
    assert payload["ok"] is False
    assert payload["error"] == "patch_requires_current_turn_path"
    assert payload["turn_id"] == "turn_old"


@pytest.mark.asyncio
async def test_patch_rejects_materialized_historical_file(tmp_path):
    runtime = RuntimeCtx(turn_id="turn_new", outdir=str(tmp_path), workdir=str(tmp_path))
    ctx = FakeBrowser(runtime)
    old_file = tmp_path / "turn_old" / "files" / "a.txt"
    old_file.parent.mkdir(parents=True, exist_ok=True)
    old_file.write_text("old", encoding="utf-8")

    state = {
        "last_decision": {
            "tool_call": {
                "params": {
                    "path": "turn_old/files/a.txt",
                    "channel": "canvas",
                    "patch": "new",
                    "kind": "display",
                }
            }
        },
        "outdir": str(tmp_path),
    }

    await handle_react_patch(react=FakeReact(), ctx_browser=ctx, state=state, tool_call_id="p_checkout")

    json_blocks = [
        b for b in ctx.timeline.blocks
        if b.get("type") == "react.tool.result" and b.get("mime") == "application/json"
    ]
    payload = json.loads(json_blocks[-1]["text"])
    assert payload["ok"] is False
    assert payload["error"] == "patch_requires_current_turn_path"
    assert old_file.read_text(encoding="utf-8") == "old"
