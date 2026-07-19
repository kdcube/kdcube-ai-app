# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Send files and links to the user out-of-band of the model's typing.

A tool result that carries a download URL puts the model in the courier role:
to show the link it must re-type an opaque signed string into its message, and
a single flipped character breaks the signature. This module is the one entry
point for the alternative: the SCENARIO that knows it holds a file or a link
delivers it straight to the chat surface as a first-class event, and the model
only refers to it in words.

Files ride the existing ``chat.files`` vertical: the event carries the OBJECT
REF (``slack:<account>:file:<id>``, ``conv:fi:...``), never a URL. The chat
widget renders a file card; activating it resolves access at click time under
the user's own session — fresh authorization, fresh short-lived link, nothing
to expire or mistype in between.

Links ride the ``chat.citations`` vertical; ``placement="chat"`` asks the chat
surface to settle the link in the conversation flow as well as the Links tab.

``deliver_result_files`` is the tool-gate helper: give it a tool result, and
when a chat lane is bound it emits the file cards and returns the result with
each download URL replaced by a delivery note the model can read. With no chat
lane (a turn-less transport) the result comes back untouched — the URL stays
the contract for machinery that clicks rather than types.
"""

from __future__ import annotations

import logging
from typing import Any, List, Mapping, Optional, Tuple

LOGGER = logging.getLogger(__name__)

# The model-facing replacement for a delivered download URL: what happened,
# what the user already sees, and what the model should (not) do.
DELIVERED_NOTE = (
    "The file was handed to the user as a file card in the chat; they open or "
    "download it there. Refer to it in words — never construct, guess, or "
    "re-type download URLs."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _filename_for(obj: Mapping[str, Any]) -> str:
    for key in ("filename", "name", "title"):
        value = _text(obj.get(key))
        if value:
            return value
    ref = _text(obj.get("object_ref") or obj.get("ref"))
    if ref:
        return ref.rsplit(":", 1)[-1] or ref
    return _text(obj.get("file_id") or obj.get("id"))


def _delivery_item(obj: Mapping[str, Any]) -> Optional[dict]:
    """One ``chat.files`` item for a file object — object ref, no URL."""
    ref = _text(obj.get("object_ref") or obj.get("ref"))
    filename = _filename_for(obj)
    if not ref or not filename:
        return None
    item: dict = {
        "object_ref": ref,
        "ref": ref,
        "filename": filename,
    }
    mime = _text(obj.get("mime") or obj.get("mime_type") or obj.get("mimetype"))
    if mime:
        item["mime"] = mime
    for key in ("size", "size_bytes"):
        value = obj.get(key)
        if isinstance(value, int) and value >= 0:
            item["size"] = value
            break
    kind = _text(obj.get("object_kind"))
    if kind:
        item["description"] = kind
    return item


def collect_file_deliveries(payload: Any) -> Tuple[Any, List[dict]]:
    """Find file objects carrying an out-of-band download URL and strip the URL.

    Walks the payload; a mapping with ``download: {encoding: "url", url: ...}``
    (the shape the slack/mail/conv named services return on turn-less
    transports) is a delivery: its ``chat.files`` item is collected and the
    download block is replaced with a delivered marker + ``DELIVERED_NOTE``.
    Returns ``(model_safe_payload, items)``; the payload is returned unchanged
    (same object) when nothing matched.
    """
    items: List[dict] = []

    def walk(node: Any) -> Any:
        if isinstance(node, Mapping):
            download = node.get("download")
            if (
                isinstance(download, Mapping)
                and _text(download.get("encoding")).lower() == "url"
                and _text(download.get("url"))
            ):
                item = _delivery_item(node)
                if item is not None:
                    items.append(item)
                    out = {k: walk(v) for k, v in node.items() if k != "download"}
                    out["download"] = {
                        "encoding": "chat",
                        "delivered": True,
                        "note": DELIVERED_NOTE,
                    }
                    return out
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    rewritten = walk(payload)
    return (rewritten if items else payload), items


async def send_files_to_user(
    items: List[Mapping[str, Any]],
    *,
    comm: Any = None,
    agent: str = "tooling",
    title: str = "",
) -> bool:
    """Emit one ``chat.files`` event for these items. Best-effort: returns
    False (and emits nothing) when no chat communicator is bound."""
    rows = [dict(item) for item in (items or []) if isinstance(item, Mapping)]
    if not rows:
        return False
    communicator = comm
    if communicator is None:
        try:
            from kdcube_ai_app.apps.chat.sdk.runtime.comm_ctx import get_comm

            communicator = get_comm()
        except Exception:
            communicator = None
    event = getattr(communicator, "event", None) if communicator is not None else None
    if not callable(event):
        return False
    try:
        result = event(
            agent=agent,
            type="chat.files",
            title=title or f"Files Ready ({len(rows)})",
            step="files",
            status="completed",
            data={"count": len(rows), "items": rows},
        )
        if hasattr(result, "__await__"):
            await result
        return True
    except Exception:
        LOGGER.info("send_files_to_user: emit failed (non-fatal)", exc_info=True)
        return False


async def send_links_to_user(
    items: List[Mapping[str, Any]],
    *,
    placement: str = "links",
    comm: Any = None,
    agent: str = "tooling",
    title: str = "",
) -> bool:
    """Emit one ``chat.citations`` event for these links.

    ``placement="chat"`` marks every item to ALSO settle in the conversation
    flow; the default keeps today's Links-tab-only behavior. Items need a
    ``url``; ``title``/``body``/``favicon`` are optional."""
    rows = []
    for item in items or []:
        if not isinstance(item, Mapping) or not _text(item.get("url")):
            continue
        row = dict(item)
        if placement == "chat":
            row["placement"] = "chat"
        rows.append(row)
    if not rows:
        return False
    communicator = comm
    if communicator is None:
        try:
            from kdcube_ai_app.apps.chat.sdk.runtime.comm_ctx import get_comm

            communicator = get_comm()
        except Exception:
            communicator = None
    event = getattr(communicator, "event", None) if communicator is not None else None
    if not callable(event):
        return False
    try:
        result = event(
            agent=agent,
            type="chat.citations",
            title=title or f"Links ({len(rows)})",
            step="citations",
            status="completed",
            data={"count": len(rows), "items": rows},
        )
        if hasattr(result, "__await__"):
            await result
        return True
    except Exception:
        LOGGER.info("send_links_to_user: emit failed (non-fatal)", exc_info=True)
        return False


async def deliver_result_files(payload: Any, *, comm: Any = None, agent: str = "tooling") -> Any:
    """The tool-gate helper: deliver a result's files to the user, return the
    model-safe result.

    Extracts download-URL file objects from ``payload``; when a chat lane is
    bound, emits them as ``chat.files`` cards and returns the payload with the
    URLs replaced by the delivery note. When there is nothing to deliver — or
    no chat lane to deliver into (turn-less transport) — the payload returns
    UNCHANGED, keeping the URL contract for clients that fetch out-of-band.
    Never raises."""
    try:
        rewritten, items = collect_file_deliveries(payload)
        if not items:
            return payload
        delivered = await send_files_to_user(items, comm=comm, agent=agent)
        if not delivered:
            return payload
        LOGGER.info(
            "deliver_result_files: %d file card(s) delivered to the user: %s",
            len(items), ", ".join(_text(i.get("object_ref")) for i in items),
        )
        return rewritten
    except Exception:
        LOGGER.info("deliver_result_files failed (non-fatal); result kept as-is", exc_info=True)
        return payload


__all__ = [
    "DELIVERED_NOTE",
    "collect_file_deliveries",
    "deliver_result_files",
    "send_files_to_user",
    "send_links_to_user",
]
