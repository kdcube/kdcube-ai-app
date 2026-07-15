# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
#
# The PULL side of the distributed turn workspace: conversation artifact refs
# (``conv:fi:`` — user attachments from any turn, files produced by code
# execution in earlier turns, external-event attachments) materialize as plain
# local files under a workspace directory. Byte resolution is the registered
# namespace byte resolver (`react/events/resolver.read_event_ref_bytes`) — the
# SAME resolution the object download action uses, so a ref that downloads
# also pulls. Framework-neutral: identity in, files out; no timeline, no
# browser, no framework runtime.

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import mimetypes


def _safe_pull_filename(name: str) -> str:
    """A ref's tail as a plain workspace filename (no separators, no traversal)."""
    raw = str(name or "").strip().replace("\\", "/").split("/")[-1]
    cleaned = "".join(ch if (ch.isalnum() or ch in "._- ") else "_" for ch in raw).strip()
    return cleaned or "pulled_file"


async def pull_refs_into_dir(
    *,
    refs: List[str],
    dest_dir: Path,
    tenant: str,
    project: str,
    user_id: str,
    conversation_id: str = "",
    storage_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Materialize conversation artifact refs as plain local files under ``dest_dir``.

    The framework-neutral core of a "pull" tool: each ref (``conv:fi:`` — a user
    attachment from any turn, a produced file from an earlier turn, an external-event
    attachment) resolves to bytes through the registered namespace byte resolver
    (`react/events/resolver.read_event_ref_bytes`, the same resolution the object
    download action uses) and is written into ``dest_dir`` under its own filename —
    e.g. an exec workspace, where generated code then reads it with a bare relative
    path. Identity fields are the request identity that owns the storage keys
    (``user_id`` is the owner: a user id or a fingerprint).

    Returns one report dict per ref: ``{"ref", "ok", "filename", "path", "size",
    "mime"}`` on success, ``{"ref", "ok": False, "error"}`` on failure — a bad ref
    never aborts the batch."""
    from kdcube_ai_app.apps.chat.sdk.solutions.react.events.resolver import (
        read_event_ref_bytes,
    )

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    reports: List[Dict[str, Any]] = []
    for raw_ref in refs or []:
        ref = str(raw_ref or "").strip()
        if not ref:
            continue
        try:
            data, meta = await read_event_ref_bytes(
                ref=ref,
                tenant=tenant,
                project=project,
                user_id=user_id,
                conversation_id=conversation_id,
                storage_path=storage_path,
            )
            filename = _safe_pull_filename(meta.get("relpath") or ref)
            target = dest / filename
            target.write_bytes(data)
            mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            reports.append({
                "ref": ref,
                "ok": True,
                "filename": filename,
                "path": str(target),
                "size": len(data),
                "mime": mime,
            })
        except Exception as error:
            reports.append({"ref": ref, "ok": False, "error": str(error)})
    return reports
