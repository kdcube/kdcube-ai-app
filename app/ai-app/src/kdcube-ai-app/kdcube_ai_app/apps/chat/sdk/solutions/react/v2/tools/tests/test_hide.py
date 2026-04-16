# SPDX-License-Identifier: MIT

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.react.proto import RuntimeCtx
from kdcube_ai_app.apps.chat.sdk.solutions.react.v2.tools.external import handle_external_tool
from kdcube_ai_app.apps.chat.sdk.solutions.react.v2.tools.hide import handle_react_hide
from kdcube_ai_app.apps.chat.sdk.solutions.react.v2.tools.tests.helpers import FakeBrowser, FakeReact


async def _render_pdf_into_timeline(monkeypatch, tmp_path):
    runtime = RuntimeCtx(turn_id="turn_hide", outdir=str(tmp_path), workdir=str(tmp_path))
    ctx = FakeBrowser(runtime)
    state = {
        "last_decision": {
            "tool_call": {
                "tool_id": "rendering_tools.write_pdf",
                "params": {
                    "path": "outputs/test/small_test.pdf",
                    "content": "<html><body>x</body></html>",
                },
            }
        },
        "outdir": str(tmp_path),
        "workdir": str(tmp_path),
    }

    async def _fake_execute_tool(**kwargs):
        path = kwargs["tool_execution_context"]["params"]["path"]
        target = kwargs["outdir"] / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"%PDF-1.4\n")
        return {"output": path, "summary": ""}

    monkeypatch.setattr(
        "kdcube_ai_app.apps.chat.sdk.solutions.react.v2.tools.external.execute_tool",
        _fake_execute_tool,
    )

    react = FakeReact()
    react.tools_subsystem = None
    await handle_external_tool(react=react, ctx_browser=ctx, state=state, tool_call_id="pdf1")
    return ctx


@pytest.mark.asyncio
async def test_react_hide_hides_rendered_pdf_artifact_path(monkeypatch, tmp_path):
    ctx = await _render_pdf_into_timeline(monkeypatch, tmp_path)
    state = {
        "last_decision": {
            "tool_call": {
                "tool_id": "react.hide",
                "params": {
                    "path": "fi:turn_hide.outputs/test/small_test.pdf",
                    "replacement": "Small PDF hidden.",
                },
            }
        }
    }

    out = await handle_react_hide(ctx_browser=ctx, state=state, tool_call_id="hide_pdf")

    payload = out.get("last_tool_result") or {}
    assert payload["status"] == "ok"
    assert payload["blocks_hidden"] >= 1
    hidden = [
        b for b in ctx.timeline.blocks
        if b.get("path") == "fi:turn_hide.outputs/test/small_test.pdf" and b.get("hidden") is True
    ]
    assert hidden
    assert "react.read(path)" in (hidden[0].get("replacement_text") or "")


@pytest.mark.asyncio
async def test_react_hide_hides_tool_result_path(monkeypatch, tmp_path):
    ctx = await _render_pdf_into_timeline(monkeypatch, tmp_path)
    state = {
        "last_decision": {
            "tool_call": {
                "tool_id": "react.hide",
                "params": {
                    "path": "tc:turn_hide.pdf1.result",
                    "replacement": "PDF generation summary hidden.",
                },
            }
        }
    }

    out = await handle_react_hide(ctx_browser=ctx, state=state, tool_call_id="hide_tc")

    payload = out.get("last_tool_result") or {}
    assert payload["status"] == "too_old"
    assert payload["blocks_hidden"] == 0
