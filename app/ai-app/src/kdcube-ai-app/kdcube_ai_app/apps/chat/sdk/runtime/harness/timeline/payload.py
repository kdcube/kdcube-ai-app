# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""Persisted conversation-timeline payload contract for agent harnesses."""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass
from typing import Any

from kdcube_ai_app.apps.chat.sdk.util import isoz


TIMELINE_KIND = "conv.timeline.v1"
SOURCES_POOL_KIND = "conv:sources_pool"


def _normalize_timestamp(value: Any) -> str:
    if isinstance(value, (int, float)):
        return (
            dt.datetime.fromtimestamp(float(value), tz=dt.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    if isinstance(value, str) and value.strip():
        return isoz(value)
    return ""


@dataclass(frozen=True)
class TimelineEventCursor:
    """Stable position of the last rendered external event in a timeline."""

    timestamp: str = ""
    event_id: str = ""
    block_path: str = ""
    block_index: int | None = None
    sequence: int | None = None
    fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.timestamp:
            out["timestamp"] = self.timestamp
        if self.event_id:
            out["event_id"] = self.event_id
        if self.block_path:
            out["block_path"] = self.block_path
        if self.block_index is not None:
            out["block_index"] = self.block_index
        if self.sequence is not None:
            out["sequence"] = self.sequence
        if self.fingerprint:
            out["fingerprint"] = self.fingerprint
        return out

    @classmethod
    def from_any(cls, raw: Any) -> "TimelineEventCursor":
        if not isinstance(raw, dict):
            return cls()
        block_index = raw.get("block_index")
        if block_index is not None:
            try:
                block_index = int(block_index)
            except (TypeError, ValueError):
                block_index = None
        sequence = raw.get("sequence")
        if sequence is not None:
            try:
                sequence = int(sequence)
            except (TypeError, ValueError):
                sequence = None
        return cls(
            timestamp=_normalize_timestamp(raw.get("timestamp")),
            event_id=str(raw.get("event_id") or "").strip(),
            block_path=str(raw.get("block_path") or "").strip(),
            block_index=block_index,
            sequence=sequence,
            fingerprint=str(raw.get("fingerprint") or "").strip(),
        )

    def is_empty(self) -> bool:
        return not (
            self.timestamp
            or self.event_id
            or self.block_path
            or self.fingerprint
        )


def extract_turn_ids_from_blocks(
    blocks: list[dict[str, Any]],
) -> list[str]:
    """Return turn IDs in first-occurrence order."""
    out: list[str] = []
    seen: set[str] = set()
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        turn_id = str(block.get("turn_id") or "").strip()
        if turn_id and turn_id not in seen:
            seen.add(turn_id)
            out.append(turn_id)
    return out


def _tail_timestamp(blocks: list[dict[str, Any]]) -> str:
    if not blocks:
        return ""
    last = blocks[-1] if isinstance(blocks[-1], dict) else None
    return _normalize_timestamp(last.get("ts")) if last else ""


def build_timeline_payload(
    *,
    blocks: list[dict[str, Any]],
    sources_pool: list[dict[str, Any]] | None = None,
    conversation_title: str | None = None,
    conversation_started_at: str | None = None,
    last_external_event_id: str | None = None,
    last_external_event_seq: int | None = None,
    last_rendered_event_cursor: TimelineEventCursor | None = None,
    cache_last_touch_at: int | None = None,
    cache_last_ttl_seconds: int | None = None,
    agent_selection_snapshot: dict[str, Any] | None = None,
    last_known_feedback_ts: str | None = None,
    include_sources_pool: bool = True,
    forked_from: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical persisted ``conv.timeline.v1`` payload."""
    return {
        "version": 1,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "blocks": list(blocks or []),
        "sources_pool": (
            list(sources_pool or []) if include_sources_pool else []
        ),
        "turn_ids": extract_turn_ids_from_blocks(blocks or []),
        "conversation_title": conversation_title or "",
        "conversation_started_at": conversation_started_at or "",
        "forked_from": (
            dict(forked_from)
            if isinstance(forked_from, dict) and forked_from
            else None
        ),
        "last_activity_at": _tail_timestamp(blocks or []),
        "last_external_event_id": last_external_event_id or "",
        "last_external_event_seq": last_external_event_seq,
        "last_rendered_event_cursor": (
            last_rendered_event_cursor.to_dict()
            if isinstance(last_rendered_event_cursor, TimelineEventCursor)
            else {}
        ),
        "cache_last_touch_at": cache_last_touch_at,
        "cache_last_ttl_seconds": cache_last_ttl_seconds,
        "agent_selection_snapshot": (
            dict(agent_selection_snapshot)
            if isinstance(agent_selection_snapshot, dict)
            else None
        ),
        "last_known_feedback_ts": last_known_feedback_ts or "",
    }


def parse_timeline_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse and normalize the canonical persisted timeline payload."""
    if not isinstance(payload, dict):
        return {}
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        blocks = []
    sources_pool = payload.get("sources_pool")
    if not isinstance(sources_pool, list):
        sources_pool = []
    last_external_event_id = payload.get("last_external_event_id")
    if isinstance(last_external_event_id, str):
        last_external_event_id = last_external_event_id.strip()
    else:
        last_external_event_id = ""
    last_external_event_seq = payload.get("last_external_event_seq")
    if last_external_event_seq is not None:
        try:
            last_external_event_seq = int(last_external_event_seq)
        except (TypeError, ValueError):
            last_external_event_seq = None
    last_rendered_event_cursor = TimelineEventCursor.from_any(
        payload.get("last_rendered_event_cursor")
    )
    turn_ids = payload.get("turn_ids")
    if not isinstance(turn_ids, list) or not turn_ids:
        turn_ids = extract_turn_ids_from_blocks(blocks)
    cache_last_touch_at = payload.get("cache_last_touch_at")
    if cache_last_touch_at is not None:
        try:
            cache_last_touch_at = int(cache_last_touch_at)
        except (TypeError, ValueError):
            cache_last_touch_at = None
    cache_last_ttl_seconds = payload.get("cache_last_ttl_seconds")
    if cache_last_ttl_seconds is not None:
        try:
            cache_last_ttl_seconds = int(cache_last_ttl_seconds)
        except (TypeError, ValueError):
            cache_last_ttl_seconds = None
    agent_selection_snapshot = payload.get("agent_selection_snapshot")
    if not isinstance(agent_selection_snapshot, dict):
        agent_selection_snapshot = None
    last_known_feedback_ts = payload.get("last_known_feedback_ts")
    if isinstance(last_known_feedback_ts, str):
        last_known_feedback_ts = last_known_feedback_ts.strip()
    else:
        last_known_feedback_ts = ""
    forked_from = payload.get("forked_from")
    if not isinstance(forked_from, dict) or not forked_from:
        forked_from = None
    return {
        "blocks": blocks,
        "sources_pool": sources_pool,
        "turn_ids": turn_ids,
        "ts": payload.get("ts"),
        "version": payload.get("version", 1),
        "conversation_title": payload.get("conversation_title") or "",
        "conversation_started_at": (
            payload.get("conversation_started_at") or ""
        ),
        "last_activity_at": payload.get("last_activity_at") or "",
        "last_external_event_id": last_external_event_id,
        "last_external_event_seq": last_external_event_seq,
        "last_rendered_event_cursor": last_rendered_event_cursor,
        "cache_last_touch_at": cache_last_touch_at,
        "cache_last_ttl_seconds": cache_last_ttl_seconds,
        "agent_selection_snapshot": agent_selection_snapshot,
        "last_known_feedback_ts": last_known_feedback_ts,
        "forked_from": forked_from,
    }
