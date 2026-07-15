# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
#
# ── attachments.py ── the multimodality seam ──
#
# NOTE: since the turn-workspace triad (turn_workspace.py), nothing is
# materialized for the model automatically — the turn frame carries metadata
# + links, and `read_file` returns visual payloads on demand. This module
# remains the mime vocabulary (_IMAGE_MIME/_DOC_MIME), the store opener, and
# a block-shaping utility for explicit multimodal needs.
#
# A turn can arrive with hosted attachments: the platform hosts the user's file at
# ingress (`store.put_attachment(role="user")`) and rides `event.user.attachment.*`
# events onto `state["external_events"]`. `execute_core` already reads the turn TEXT
# (`external_events_text`); this seam reads the ATTACHMENTS alongside it and turns
# the supported ones (images + PDFs) into model content blocks.
#
# The block shape is KDCube's native multimodal block —
# `{"type":"image","data":<b64>,"media_type":<mime>}` (and the `document` variant
# for PDFs). It flows verbatim into a LangChain `HumanMessage.content` list; the
# model bridge (`KDCubeChatModel` -> `stream_model_text_tracked`) then normalizes
# it per provider (Anthropic `source` block / OpenAI `image_url` data URI) via the
# shared `message_utils.normalize_blocks`. So a ported agent stays provider-agnostic
# and never touches a provider SDK to be multimodal.
#
# Materialization is fail-open: an attachment we cannot read (no bytes, no store,
# unsupported mime) is skipped, never fatal — a turn with an unreadable image still
# answers from its text.

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List

from kdcube_ai_app.apps.chat.sdk.protocol import hosted_external_event_attachments
from kdcube_ai_app.infra.service_hub.multimodality import normalize_image_base64_for_model

LOGGER = logging.getLogger("kdcube.ported_langgraph_agents.attachments")

# The mimes we can hand a vision/document model. Mirrors
# multimodality.MODALITY_IMAGE_MIME / MODALITY_DOC_MIME.
_IMAGE_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_DOC_MIME = {"application/pdf"}


def _open_conversation_store() -> Any:
    """Open the platform conversation store used to read hosted attachment bytes.

    Constructed the same way ReAct's attachment hydration does
    (`ConversationStore(get_settings().STORAGE_PATH)`), so a hosted attachment's
    `hosted_uri` resolves through the same storage backend that wrote it. Returns
    None offline / when storage is unavailable — the caller then skips bytes it
    cannot fetch."""
    try:
        from kdcube_ai_app.apps.chat.sdk.config import get_settings
        from kdcube_ai_app.apps.chat.sdk.storage.conversation_store import ConversationStore

        return ConversationStore(get_settings().STORAGE_PATH)
    except Exception:
        return None


async def materialize_turn_attachments(events: Any) -> List[Dict[str, Any]]:
    """Read this turn's hosted attachments into model content blocks.

    Returns a list of native multimodal blocks
    (`{"type":"image"|"document","data":<b64>,"media_type":<mime>}`) for every
    supported attachment. Prefers a base64 body already carried on the event;
    otherwise fetches the bytes from `hosted_uri` via the platform store. Images
    are downscaled through `normalize_image_base64_for_model` so an oversized edge
    is bounded before the model sees it. Unsupported / unreadable attachments are
    skipped cleanly (never fatal)."""
    raw = hosted_external_event_attachments(events or [])
    LOGGER.info("[ported-langgraph] attachments: %d hosted attachment(s) on this turn", len(raw))
    if not raw:
        return []

    blocks: List[Dict[str, Any]] = []
    store = None  # lazily opened only if some attachment needs a byte fetch
    for item in raw:
        if not isinstance(item, dict):
            continue
        mime = str(item.get("mime") or item.get("mime_type") or "").strip().lower()
        is_image = mime in _IMAGE_MIME
        is_doc = mime in _DOC_MIME
        if not (is_image or is_doc):
            LOGGER.info(
                "[ported-langgraph] attachment SKIP: unsupported mime=%r (not image/pdf)", mime
            )
            # Skip anything we cannot hand a vision/document model.
            continue

        b64 = item.get("base64")
        if not b64:
            hosted_uri = str(item.get("hosted_uri") or "").strip()
            if not hosted_uri:
                LOGGER.info("[ported-langgraph] attachment SKIP: no base64 and no hosted_uri mime=%r", mime)
                continue
            if store is None:
                store = _open_conversation_store()
            if store is None:
                LOGGER.warning(
                    "[ported-langgraph] attachment SKIP: conversation store unavailable, cannot fetch uri=%r",
                    hosted_uri,
                )
                continue
            try:
                data = await store.get_blob_bytes(hosted_uri)
            except Exception:
                LOGGER.warning(
                    "[ported-langgraph] attachment fetch failed uri=%r", hosted_uri, exc_info=True
                )
                continue
            b64 = base64.b64encode(data).decode("ascii")
            LOGGER.info("[ported-langgraph] attachment fetched %d bytes uri=%r mime=%r", len(data), hosted_uri, mime)

        if is_image:
            try:
                normalized = normalize_image_base64_for_model(b64, media_type=mime)
                b64 = normalized.get("base64") or b64
            except Exception:
                pass
            blocks.append({"type": "image", "data": b64, "media_type": mime})
        else:
            blocks.append({"type": "document", "data": b64, "media_type": mime})

    LOGGER.info(
        "[ported-langgraph] attachments materialized: %d model block(s) from %d hosted attachment(s)",
        len(blocks), len(raw),
    )
    return blocks


def to_human_message_content(text: str, attachments: List[Dict[str, Any]]) -> Any:
    """Shape a user turn into a LangChain `HumanMessage.content`.

    Text-only (no attachments) stays a PLAIN STRING — no behavior change for the
    common case. With attachments the content becomes a multimodal block list
    `[{"type":"text","text":...}, <image/document blocks...>]`."""
    text = text or ""
    if not attachments:
        return text
    return [{"type": "text", "text": text}, *attachments]
