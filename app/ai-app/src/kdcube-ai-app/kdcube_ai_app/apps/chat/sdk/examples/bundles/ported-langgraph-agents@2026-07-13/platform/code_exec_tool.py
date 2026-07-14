# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
#
# ── code_exec_tool.py ── the model-callable `run_python` tool ──
#
# A plain LangChain `@tool` both ported agents can bind: the model writes Python,
# this tool runs it in the isolated sandbox (via platform/code_exec.py), and every
# file the code produces is hosted into KDCube's conversation storage EXACTLY like
# a user attachment. The tool returns a CONCISE TEXT result — truncated
# stdout/stderr plus REFERENCES to the created files (rn + filename + mime). The
# file BYTES are never in the message, only the refs (the same discipline the
# React agent's `host_files` keeps).
#
# The tool is inert unless it runs inside an active `code_exec_scope` (entered by
# `execute_core` around the graph run). Offline / disabled, it fails open with a
# short message and the turn still answers.

from __future__ import annotations

import logging
from typing import Any, List

from langchain_core.tools import tool

LOGGER = logging.getLogger("kdcube.ported_langgraph_agents.code_exec")

# Bytes cap on stdout/stderr folded into the model-visible result (the authoritative
# large outputs are the hosted files, not the message).
_STREAM_PREVIEW_MAX = 4000


def _truncate(text: str, limit: int = _STREAM_PREVIEW_MAX) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def _format_result(result: dict) -> str:
    ok = bool(result.get("ok"))
    lines: List[str] = [f"Status: {'success' if ok else 'error'}"]

    if not ok:
        # Propagate the error CLASSIFICATION so the model reacts correctly: a runtime/
        # sandbox failure is a platform problem it may retry; a program error is its own
        # code and must be fixed. (See docs/exec/exec-logging-error-propagation-README.md.)
        kind = str(result.get("error_kind") or "").strip().lower()
        code = str(result.get("error") or "").strip()
        msg = str(result.get("error_message") or result.get("stderr") or "").strip()
        if kind == "runtime":
            lines.append(
                f"Runtime/sandbox error ({code or 'sandbox_execution_failed'}) — a PLATFORM problem, "
                f"not a defect in your code; usually transient, so you MAY RETRY."
            )
            if msg:
                lines.append(f"Details: {msg}")
        elif kind == "program":
            lines.append(
                f"Program error ({code or 'program_error'}) — YOUR code raised. Read the program log "
                f"below, fix the code, and retry."
            )
            if msg:
                lines.append(f"Details: {msg}")
        elif code or msg:
            lines.append(f"Error{f' ({code})' if code else ''}: {msg}".rstrip())

    files = result.get("files") or []
    if files:
        lines.append(
            f"Created files ({len(files)}) — hosted and delivered to the user. Reference each "
            f"by its link so the user can download it:"
        )
        for f in files:
            rn = str(f.get("rn") or "").strip()
            link = str(f.get("logical_path") or "").strip()
            filename = str(f.get("filename") or "").strip() or "(file)"
            mime = str(f.get("mime") or "").strip() or "application/octet-stream"
            # Prefer the downloadable `fi:conv_…` link (what the chat UI resolves);
            # fall back to the rn if the link is unavailable.
            ref = f"link={link}" if link else f"rn={rn}"
            lines.append(f"- {filename} [{mime}] {ref}")
    else:
        lines.append("Created files: none")

    stdout = _truncate(str(result.get("stdout") or "").strip())
    if stdout:
        lines.append("stdout (tail):")
        lines.append(stdout)
    stderr = _truncate(str(result.get("stderr") or "").strip())
    if stderr:
        lines.append("stderr (tail):")
        lines.append(stderr)
    return "\n".join(lines).strip()


def build_run_python_tool() -> Any:
    """Return the `run_python` LangChain tool (a fresh object per call, so each
    agent binds its own instance)."""

    @tool
    async def run_python(code: str) -> str:
        """Run a Python 3 program in an isolated sandbox and keep the files it
        creates.

        Use this to compute, transform data, generate files (CSV, JSON, images,
        charts, reports), or explore files. Write any file you want to KEEP with a
        plain relative path — e.g. ``open("summary.csv", "w").write(...)`` — and it
        is hosted and delivered to the user automatically; the working directory is
        already the deliverables folder. Top-level ``await`` is allowed. Network
        access is disabled.

        Returns a short report: success/error, the created files as references
        (filename + mime + a downloadable link — reference each file by its link so
        the user can download it), and truncated stdout/stderr. Large outputs must be
        written to files, not printed.
        """
        # Lazy, package-relative import: keeps this module import-light and avoids
        # pulling the exec seam into offline tool-list construction.
        from .code_exec import run_code_and_host

        LOGGER.info("[ported-langgraph] run_python: model invoked the tool (code_len=%d)", len(code or ""))
        result = await run_code_and_host(code)
        report = _format_result(result)
        LOGGER.info(
            "[ported-langgraph] run_python: returning report to model (ok=%s files=%d report_len=%d)",
            bool(result.get("ok")), len(result.get("files") or []), len(report),
        )
        return report

    return run_python
