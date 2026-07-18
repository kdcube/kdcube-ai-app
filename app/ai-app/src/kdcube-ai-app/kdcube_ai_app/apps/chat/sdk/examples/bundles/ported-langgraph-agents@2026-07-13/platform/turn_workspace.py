# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
#
# ── turn_workspace.py ── the turn's distributed workspace, model-facing ──
#
# KDCube gives every turn a DISTRIBUTED WORKSPACE — per-turn `work/` + `out/`
# directories on the shared exec-workspace volume (the same concept the React
# agent stands on: `get_exec_workspace_root`, `OUTDIR_CV`/`WORKDIR_CV`, hosting
# through `ApplicationHostingService`). The workspace follows ONE rule with no
# exceptions: it starts EMPTY every turn, and a file enters it only through an
# EXPLICIT PULL — including files arriving with the current message. The agent
# pulls what it needs by conversation link (`conv:fi:`), reads/processes it
# with code execution, and everything its code writes is hosted back into the
# conversation. Uniform semantics: current-turn files, earlier-turn files, and
# the agent's own produced files are all the same thing — a link to pull.
#
# The model learns all of this IN-BAND, the way React's timeline frames its
# input (`turn.header` / `user.prompt` blocks): each turn's text is framed as
#
#     [Turn start turn_<id>]      <- the boundary + the empty-workspace rule
#     [User message]              <- the user's words, verbatim
#     [Files arriving this turn]  <- METADATA ONLY: filename, mime, size, LINK
#
# NOTHING is read for the model automatically — not text, not images. The
# frame carries metadata + the link; the model decides: `read_file` to view a
# file (text or visual, exactly like react.read), `pull_files` + `run_python`
# to process it. Same triad as React: read / pull / exec over links. Without
# the in-band frame the model trusts stale history ("I pulled that file
# before, it is still here").
#
# This module is the bundle's model-facing door to that workspace:
#
#   * `prepare_turn_workspace` — account for EVERY file arriving this turn:
#     metadata as received (filename, mime, size) + its durable conversation
#     link, and — when the workspace is not available — the honest reason its
#     contents cannot be examined. A file is never silently dropped.
#   * `frame_turn_input` — the framed turn text above.
#   * `build_read_file_tool` — the view door: one conversation file into
#     visible context by its link (text bounded; images/PDF as visual
#     payloads, downscaled under a byte cap — react.read semantics).
#   * `build_pull_files_tool` — the materialize door: ANY conversation file
#     into the working directory by its `conv:fi:` link. Byte resolution for
#     both doors is the shared SDK core (the namespace byte resolver
#     `read_event_ref_bytes` — the same resolution the file-download action
#     uses; pull adds `runtime/harness/workspace.pull_refs_into_dir` on top).
#
# Fail-open per file, never per turn: a link that cannot be pulled is reported
# by the pull result, and the turn proceeds.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List

from langchain_core.tools import tool

from kdcube_ai_app.apps.chat.sdk.protocol import hosted_external_event_attachments

LOGGER = logging.getLogger("kdcube.ported_langgraph_agents.turn_workspace")


def _human_size(size: int) -> str:
    value = float(max(0, int(size or 0)))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(value)} B"


@dataclass
class TurnFile:
    """One arriving file's account this turn — the model hears exactly this."""
    filename: str
    mime: str
    size: int
    # The file's durable conversation link (`conv:fi:<turn>.user.attachments/<name>`,
    # the same shape the turn recorder / Files tab carry) — THE pull handle, this
    # turn and in every later one. It rides the turn frame into checkpointed history.
    ref: str = ""
    # Set when the workspace is unavailable: why the contents cannot be examined.
    reason: str = ""


@dataclass
class TurnWorkspace:
    """This turn's workspace state and the files that arrived with the turn."""
    live: bool
    files: List[TurnFile] = field(default_factory=list)
    # The current turn's id — stamped into the turn frame so the model anchors
    # "now" against the turn segments inside conv:fi: links (its history spans
    # many turns; the working directory belongs to exactly this one).
    turn_id: str = ""


async def prepare_turn_workspace(
    ctx: Any,
    events: Any,
    *,
    exec_tool_bound: bool,
) -> TurnWorkspace:
    """Account for every hosted attachment arriving this turn.

    No bytes move here — the workspace starts empty and STAYS empty until the
    model pulls (one rule, no current-turn exception). ``ctx`` is the code-exec
    context (`build_code_exec_context`); `exec_tool_bound` reflects whether
    `run_python` is actually bound this turn (admin-declared and not
    user-disabled) — with no workspace tools the files are honestly reported
    as not examinable this turn."""
    hosted = hosted_external_event_attachments(events or [])
    live = bool(ctx is not None and getattr(ctx, "enabled", False) and exec_tool_bound)
    workspace = TurnWorkspace(live=live, turn_id=str(getattr(ctx, "turn_id", "") or "").strip())
    if not hosted:
        return workspace

    for item in hosted:
        if not isinstance(item, dict):
            continue
        mime = str(item.get("mime") or "application/octet-stream").strip().lower()
        raw_filename = str(item.get("filename") or "").strip()
        entry = TurnFile(
            filename=raw_filename or "attachment",
            mime=mime,
            size=int(item.get("size") or 0),
            ref=(
                f"conv:fi:{workspace.turn_id}.user.attachments/{raw_filename}"
                if workspace.turn_id and raw_filename
                else ""
            ),
        )
        if not live:
            entry.reason = "no workspace tools are active this turn (code execution is not enabled)"
        workspace.files.append(entry)
        LOGGER.info(
            "[ported-langgraph] turn workspace: arriving file %s (%s, %d bytes) ref=%s live=%s",
            entry.filename, entry.mime, entry.size, entry.ref or "-", live,
        )
    return workspace


def frame_turn_input(question: str, workspace: TurnWorkspace) -> str:
    """The model's turn text, framed like React frames its timeline input:
    turn-start header (boundary + the empty-workspace rule), the user's
    message verbatim, and the arriving-files block with a pull link per file.

    Emitted every turn the workspace is live (files or not) — the boundary
    must be in-band. Without a workspace and without files the user's text
    passes through unframed (there is nothing to explain)."""
    question = question or ""
    if not workspace.live and not workspace.files:
        return question
    header = f"[Turn start {workspace.turn_id}]" if workspace.turn_id else "[Turn start]"
    parts: List[str] = []
    if workspace.live:
        parts.append(
            header + "\n"
            "Your working directory is EMPTY — it starts fresh every turn. Files are "
            "given to you as LINKS only; nothing is read for you automatically. To VIEW "
            "a file, call read_file with its conversation link. To PROCESS it with code, "
            "call pull_files with the link, then read it from run_python by the bare "
            "filename the pull reports."
        )
    else:
        parts.append(header)
    parts.append("[User message]\n" + question)
    if workspace.files:
        lines = ["[Files arriving this turn]"]
        for f in workspace.files:
            head = f"- {f.filename} ({f.mime}, {_human_size(f.size)})"
            if workspace.live and f.ref:
                lines.append(f"{head} — link: {f.ref}")
            elif f.reason:
                lines.append(
                    f"{head} — received and stored with the conversation, but {f.reason}; its "
                    f"contents are not available to you right now — tell the user plainly when "
                    f"it matters." + (f" Conversation link: {f.ref}" if f.ref else "")
                )
            else:
                lines.append(f"{head} — link: {f.ref}" if f.ref else f"{head} — received.")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def build_pull_files_tool() -> Any:
    """Return the `pull_files` LangChain tool (a fresh object per call, so each
    agent binds its own instance). Bound beside `run_python` — it feeds the
    same workspace working directory the code reads."""

    @tool
    async def pull_files(paths: List[str]) -> str:
        """Materialize conversation files into your run_python working directory.

        This is how ANY file becomes readable by your code: files attached to
        the current message (their pull links are in `[Files arriving this
        turn]`), user attachments from earlier turns, and files you produced
        with run_python before (its report listed each as ``link=conv:fi:...``).
        Pass each ``conv:fi:`` link exactly as it appears in the conversation;
        then read the file from run_python with the bare filename this tool
        reports.

        The working directory starts EMPTY every turn — nothing from earlier
        turns is in it until you pull it again.
        """
        from kdcube_ai_app.apps.chat.sdk.runtime.harness.workspace import pull_refs_into_dir
        from .code_exec import current_code_exec_context, exec_files_dir

        ctx = current_code_exec_context()
        if ctx is None or not ctx.enabled:
            return "The code workspace is not available for this turn (code execution disabled or offline)."
        files_dir = exec_files_dir(ctx)
        if files_dir is None:
            return "The code workspace is not available for this turn (no working directory)."

        LOGGER.info("[ported-langgraph] pull_files: %d ref(s) requested", len(paths or []))
        reports = await pull_refs_into_dir(
            refs=list(paths or []),
            dest_dir=files_dir,
            tenant=ctx.tenant,
            project=ctx.project,
            user_id=ctx.user_id,
            conversation_id=ctx.conversation_id,
        )
        if not reports:
            return "No refs were pulled — pass one or more conv:fi: links exactly as shown in the conversation."
        lines: List[str] = []
        for report in reports:
            if report.get("ok"):
                lines.append(
                    f"- pulled {report['filename']} ({report.get('mime')}, {_human_size(report.get('size') or 0)}) — "
                    f"read it from run_python as ./{report['filename']}"
                )
            else:
                lines.append(f"- FAILED {report.get('ref')}: {report.get('error')}")
        ok_count = sum(1 for r in reports if r.get("ok"))
        LOGGER.info("[ported-langgraph] pull_files: %d/%d ref(s) materialized", ok_count, len(reports))
        return "\n".join([f"Pulled {ok_count}/{len(reports)} file(s) into the working directory:"] + lines)

    return pull_files


# react.read-mirroring caps: bounded text view; images/PDF ride as visual
# payloads only under a byte cap (oversized images are downscaled first).
_READ_TEXT_CAP = 60_000
_READ_BLOB_CAP = 4 * 1024 * 1024

_TEXTUAL_MIME_PREFIXES = ("text/",)
_TEXTUAL_MIME_EXACT = {
    "application/json", "application/xml", "application/x-yaml",
    "application/yaml", "application/csv", "application/x-ndjson",
    "application/javascript", "application/sql",
}


def _is_textual_mime(mime: str) -> bool:
    mime = (mime or "").strip().lower()
    return mime.startswith(_TEXTUAL_MIME_PREFIXES) or mime in _TEXTUAL_MIME_EXACT


def build_read_file_tool() -> Any:
    """Return the `read_file` LangChain tool (fresh per call). The VIEW door of
    the workspace triad, mirroring react.read: text in, visuals in, binaries
    routed to pull+exec."""

    @tool
    async def read_file(path: str, max_text_symbols: int = 0) -> Any:
        """Read ONE conversation file into your visible context by its conv:fi: link.

        Text files return their text (bounded). Images and PDFs are returned to
        you as visual content (oversized images are downscaled). Other binary
        files are not viewable this way — use pull_files + run_python to
        process them. Links appear in `[Files arriving this turn]` and in
        run_python reports (``link=conv:fi:...``); pass the link exactly as
        shown. `max_text_symbols` optionally lowers the text bound.
        """
        from kdcube_ai_app.apps.chat.sdk.runtime.harness.events.resolver import read_event_ref_bytes
        from .attachments import _DOC_MIME, _IMAGE_MIME
        from .code_exec import current_code_exec_context

        ctx = current_code_exec_context()
        if ctx is None or not ctx.enabled:
            return "The workspace tools are not available for this turn (code execution disabled or offline)."
        ref = str(path or "").strip()
        if not ref:
            return "Pass one conv:fi: link exactly as shown in the conversation."
        try:
            data, meta = await read_event_ref_bytes(
                ref=ref,
                tenant=ctx.tenant,
                project=ctx.project,
                user_id=ctx.user_id,
                conversation_id=ctx.conversation_id,
            )
        except Exception as error:
            LOGGER.warning("[ported-langgraph] read_file failed ref=%r", ref, exc_info=True)
            return f"Could not read {ref}: {error}"

        import mimetypes as _mt
        from pathlib import PurePosixPath as _P

        filename = _P(str(meta.get("relpath") or ref)).name or "file"
        mime = (_mt.guess_type(filename)[0] or "application/octet-stream").lower()
        head = f"read {filename} ({mime}, {_human_size(len(data))}) from {ref}"
        LOGGER.info("[ported-langgraph] read_file: %s", head)

        if _is_textual_mime(mime):
            cap = max(1, int(max_text_symbols)) if max_text_symbols else _READ_TEXT_CAP
            text = data.decode("utf-8", errors="replace")
            clipped = text[:cap] + ("\n...[truncated]" if len(text) > cap else "")
            return f"[{head}]\n{clipped}"

        if mime in _IMAGE_MIME:
            import base64 as _b64
            from kdcube_ai_app.infra.service_hub.multimodality import normalize_image_base64_for_model

            b64 = _b64.b64encode(data).decode("ascii")
            try:
                normalized = normalize_image_base64_for_model(b64, media_type=mime)
                b64 = normalized.get("base64") or b64
            except Exception:
                pass
            if len(b64) > _READ_BLOB_CAP:
                return (
                    f"[{head}] The image is too large for visible context — "
                    f"pull_files it and process it with run_python instead."
                )
            return [
                {"type": "text", "text": f"[{head}]"},
                {"type": "image", "data": b64, "media_type": mime},
            ]

        if mime in _DOC_MIME:
            import base64 as _b64

            if len(data) > _READ_BLOB_CAP:
                return (
                    f"[{head}] The PDF is too large for visible context — "
                    f"pull_files it and process it with run_python instead."
                )
            return [
                {"type": "text", "text": f"[{head}]"},
                {"type": "document", "data": _b64.b64encode(data).decode("ascii"), "media_type": mime},
            ]

        return (
            f"[{head}] This is a binary file and is not viewable directly — "
            f"pull_files it and examine it with run_python."
        )

    return read_file
