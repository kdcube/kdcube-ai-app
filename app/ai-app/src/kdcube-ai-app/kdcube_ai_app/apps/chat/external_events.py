# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from kdcube_ai_app.apps.chat.sdk.continuations import ContinuationKind
from kdcube_ai_app.infra.namespaces import REDIS, ns_key


_DEFAULT_OWNER_TTL_SECONDS = 600


@dataclass
class ConversationExternalEvent:
    message_id: str
    kind: ContinuationKind | str
    created_at: float
    sequence: int
    stream_id: Optional[str] = None
    explicit: bool = False
    target_turn_id: Optional[str] = None
    active_turn_id_at_ingress: Optional[str] = None
    owner_turn_id: Optional[str] = None
    source: str = ""
    text: str = ""
    payload: Optional[Dict[str, Any]] = None
    task_payload: Optional[Dict[str, Any]] = None
    consumed_at: Optional[float] = None
    consumed_by_turn_id: Optional[str] = None
    promoted_at: Optional[float] = None
    promoted_task_id: Optional[str] = None
    failed_at: Optional[float] = None
    failed_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "kind": str(self.kind or "external"),
            "created_at": float(self.created_at or 0.0),
            "sequence": int(self.sequence or 0),
            "stream_id": self.stream_id,
            "explicit": bool(self.explicit),
            "target_turn_id": self.target_turn_id,
            "active_turn_id_at_ingress": self.active_turn_id_at_ingress,
            "owner_turn_id": self.owner_turn_id,
            "source": self.source or "",
            "text": self.text or "",
            "payload": dict(self.payload or {}),
            "task_payload": dict(self.task_payload or {}),
            "consumed_at": float(self.consumed_at) if self.consumed_at is not None else None,
            "consumed_by_turn_id": self.consumed_by_turn_id,
            "promoted_at": float(self.promoted_at) if self.promoted_at is not None else None,
            "promoted_task_id": self.promoted_task_id,
            "failed_at": float(self.failed_at) if self.failed_at is not None else None,
            "failed_reason": self.failed_reason,
        }

    @classmethod
    def from_any(cls, raw: Any) -> "ConversationExternalEvent":
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict):
            raise TypeError(f"Unsupported external event payload: {type(raw)!r}")
        return cls(
            message_id=str(raw.get("message_id") or ""),
            kind=str(raw.get("kind") or "external"),
            created_at=float(raw.get("created_at") or 0.0),
            sequence=int(raw.get("sequence") or 0),
            stream_id=raw.get("stream_id"),
            explicit=bool(raw.get("explicit")),
            target_turn_id=raw.get("target_turn_id"),
            active_turn_id_at_ingress=raw.get("active_turn_id_at_ingress"),
            owner_turn_id=raw.get("owner_turn_id"),
            source=str(raw.get("source") or ""),
            text=str(raw.get("text") or ""),
            payload=dict(raw.get("payload") or {}),
            task_payload=dict(raw.get("task_payload") or {}),
            consumed_at=(float(raw.get("consumed_at")) if raw.get("consumed_at") is not None else None),
            consumed_by_turn_id=raw.get("consumed_by_turn_id"),
            promoted_at=(float(raw.get("promoted_at")) if raw.get("promoted_at") is not None else None),
            promoted_task_id=raw.get("promoted_task_id"),
            failed_at=(float(raw.get("failed_at")) if raw.get("failed_at") is not None else None),
            failed_reason=raw.get("failed_reason"),
        )

    def task_payload_model(self):
        from kdcube_ai_app.apps.chat.sdk.protocol import ChatTaskPayload

        return ChatTaskPayload.model_validate(self.task_payload or {})


@dataclass
class TimelineOwnerLease:
    turn_id: str
    bundle_id: str = ""
    instance_id: str = ""
    process_id: int = 0
    listener_id: str = ""
    started_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id or "",
            "bundle_id": self.bundle_id or "",
            "instance_id": self.instance_id or "",
            "process_id": int(self.process_id or 0),
            "listener_id": self.listener_id or "",
            "started_at": self.started_at or "",
            "updated_at": self.updated_at or "",
        }

    @classmethod
    def from_any(cls, raw: Any) -> Optional["TimelineOwnerLease"]:
        if raw is None:
            return None
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict):
            return None
        turn_id = str(raw.get("turn_id") or "").strip()
        if not turn_id:
            return None
        return cls(
            turn_id=turn_id,
            bundle_id=str(raw.get("bundle_id") or ""),
            instance_id=str(raw.get("instance_id") or ""),
            process_id=int(raw.get("process_id") or 0),
            listener_id=str(raw.get("listener_id") or ""),
            started_at=str(raw.get("started_at") or ""),
            updated_at=str(raw.get("updated_at") or ""),
        )


class RedisConversationExternalEventSource:
    def __init__(self, *, redis, tenant: str, project: str, conversation_id: str):
        self.redis = redis
        self.tenant = tenant
        self.project = project
        self.conversation_id = conversation_id

    @property
    def log_key(self) -> str:
        base = ns_key(REDIS.CHAT.CONVERSATION_EXTERNAL_EVENTS_PREFIX, tenant=self.tenant, project=self.project)
        return f"{base}:{self.conversation_id}"

    @property
    def sequence_key(self) -> str:
        base = ns_key(REDIS.CHAT.CONVERSATION_EXTERNAL_EVENTS_SEQ_PREFIX, tenant=self.tenant, project=self.project)
        return f"{base}:{self.conversation_id}"

    def event_key(self, message_id: str) -> str:
        return f"{self.log_key}:event:{str(message_id or '').strip()}"

    def claim_key(self, message_id: str) -> str:
        return f"{self.log_key}:claim:{str(message_id or '').strip()}"

    @property
    def promotion_cursor_key(self) -> str:
        return f"{self.log_key}:promotion-cursor"

    @property
    def owner_key(self) -> str:
        base = ns_key(REDIS.CHAT.CONVERSATION_TIMELINE_OWNER_PREFIX, tenant=self.tenant, project=self.project)
        return f"{base}:{self.conversation_id}"

    async def publish(
        self,
        *,
        kind: ContinuationKind | str,
        explicit: bool = False,
        target_turn_id: Optional[str] = None,
        active_turn_id_at_ingress: Optional[str] = None,
        owner_turn_id: Optional[str] = None,
        source: str = "",
        text: str = "",
        payload: Optional[Dict[str, Any]] = None,
        task_payload: Optional[Dict[str, Any]] = None,
    ) -> ConversationExternalEvent:
        sequence = int(await self.redis.incr(self.sequence_key))
        event = ConversationExternalEvent(
            message_id=f"evt_{uuid.uuid4().hex[:10]}",
            kind=str(kind or "external"),
            created_at=time.time(),
            sequence=sequence,
            explicit=explicit,
            target_turn_id=target_turn_id,
            active_turn_id_at_ingress=active_turn_id_at_ingress,
            owner_turn_id=owner_turn_id,
            source=source or "",
            text=text or "",
            payload=dict(payload or {}),
            task_payload=dict(task_payload or {}),
        )
        stream_id = await self._append_to_stream(event)
        event.stream_id = str(stream_id or "")
        await self._write_event(event)
        return event

    async def read_since(self, cursor: str | int | None, *, limit: Optional[int] = None) -> List[ConversationExternalEvent]:
        raw_items = await self._stream_read_since(cursor, limit=limit)
        out: List[ConversationExternalEvent] = []
        for raw in raw_items or []:
            try:
                item = await self._read_event_ref(raw)
            except Exception:
                continue
            if item is None:
                continue
            out.append(item)
            if limit is not None and len(out) >= int(limit):
                break
        return out

    async def wait_for_events_after(
        self,
        cursor: str | int | None,
        *,
        block_ms: int = 3000,
        limit: Optional[int] = None,
    ) -> List[ConversationExternalEvent]:
        raw_items = await self._stream_wait_for_after(cursor, block_ms=block_ms, limit=limit)
        out: List[ConversationExternalEvent] = []
        for raw in raw_items or []:
            try:
                item = await self._read_event_ref(raw)
            except Exception:
                continue
            if item is None:
                continue
            out.append(item)
            if limit is not None and len(out) >= int(limit):
                break
        return out

    async def claim_next_promotable(
        self,
        *,
        claimant_id: str,
        ttl_seconds: int = 120,
    ) -> Optional[ConversationExternalEvent]:
        cursor = await self._get_promotion_cursor()
        raw_items = await self._stream_read_since(cursor, limit=200)
        last_terminal_stream_id = str(cursor or "")
        for raw in raw_items or []:
            item = await self._read_event_ref(raw)
            if item is None:
                continue
            stream_id = str(item.stream_id or "")
            if item.failed_at is not None:
                if stream_id:
                    last_terminal_stream_id = stream_id
                continue
            if item.task_payload is None:
                if stream_id:
                    last_terminal_stream_id = stream_id
                continue
            if item.promoted_at is not None:
                if stream_id:
                    last_terminal_stream_id = stream_id
                continue
            if item.consumed_at is not None:
                if stream_id:
                    last_terminal_stream_id = stream_id
                continue
            if last_terminal_stream_id:
                await self._advance_promotion_cursor(last_terminal_stream_id)
            if not await self._claim_event(item.message_id, claimant_id=claimant_id, ttl_seconds=ttl_seconds):
                continue
            latest = await self.get_event(item.message_id)
            if latest is None:
                await self.release_claim(message_id=item.message_id, claimant_id=claimant_id)
                continue
            if latest.failed_at is not None or latest.promoted_at is not None or latest.consumed_at is not None:
                if latest.stream_id:
                    await self._advance_promotion_cursor(str(latest.stream_id))
                await self.release_claim(message_id=item.message_id, claimant_id=claimant_id)
                continue
            return latest
        if raw_items:
            tail = await self._read_event_ref(raw_items[-1])
            if tail is not None and tail.stream_id:
                await self._advance_promotion_cursor(str(tail.stream_id))
        return None

    async def get_event(self, message_id: str) -> Optional[ConversationExternalEvent]:
        raw = await self.redis.get(self.event_key(message_id))
        if raw is None:
            return None
        try:
            return ConversationExternalEvent.from_any(raw)
        except Exception:
            return None

    async def release_claim(self, *, message_id: str, claimant_id: str) -> None:
        raw = await self.redis.get(self.claim_key(message_id))
        if raw is None:
            return
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if claimant_id and str(raw or "") != str(claimant_id):
            return
        await self.redis.delete(self.claim_key(message_id))

    async def mark_promoted(self, *, message_id: str, claimant_id: str, task_id: str) -> Optional[ConversationExternalEvent]:
        event = await self.get_event(message_id)
        if event is None:
            await self.release_claim(message_id=message_id, claimant_id=claimant_id)
            return None
        event.promoted_at = time.time()
        event.promoted_task_id = str(task_id or "")
        await self._write_event(event)
        if event.stream_id:
            await self._advance_promotion_cursor(str(event.stream_id))
        await self.release_claim(message_id=message_id, claimant_id=claimant_id)
        return event

    async def mark_failed(self, *, message_id: str, claimant_id: str, reason: str) -> Optional[ConversationExternalEvent]:
        event = await self.get_event(message_id)
        if event is None:
            await self.release_claim(message_id=message_id, claimant_id=claimant_id)
            return None
        event.failed_at = time.time()
        event.failed_reason = str(reason or "failed")
        await self._write_event(event)
        if event.stream_id:
            await self._advance_promotion_cursor(str(event.stream_id))
        await self.release_claim(message_id=message_id, claimant_id=claimant_id)
        return event

    async def mark_consumed_up_to(self, *, max_sequence: int, turn_id: str) -> int:
        max_sequence = int(max_sequence or 0)
        if max_sequence <= 0:
            return 0
        updated = 0
        raw_items = await self._stream_read_all()
        max_stream_id = ""
        for raw in raw_items or []:
            item = await self._read_event_ref(raw)
            if item is None:
                continue
            if int(item.sequence or 0) > max_sequence:
                continue
            if item.consumed_at is not None:
                continue
            if item.failed_at is not None:
                continue
            item.consumed_at = time.time()
            item.consumed_by_turn_id = str(turn_id or "")
            await self._write_event(item)
            if item.stream_id:
                max_stream_id = str(item.stream_id)
            updated += 1
        if max_stream_id:
            await self._advance_promotion_cursor(max_stream_id)
        return updated

    async def get_owner(self) -> Optional[TimelineOwnerLease]:
        raw = await self.redis.get(self.owner_key)
        return TimelineOwnerLease.from_any(raw)

    async def acquire_owner(
        self,
        *,
        turn_id: str,
        bundle_id: str = "",
        listener_id: str = "",
        ttl_seconds: int = _DEFAULT_OWNER_TTL_SECONDS,
    ) -> TimelineOwnerLease:
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        lease = TimelineOwnerLease(
            turn_id=turn_id or "",
            bundle_id=bundle_id or "",
            instance_id=os.getenv("INSTANCE_ID", "unknown"),
            process_id=os.getpid(),
            listener_id=listener_id or f"listener_{uuid.uuid4().hex[:8]}",
            started_at=now_iso,
            updated_at=now_iso,
        )
        await self.redis.setex(
            self.owner_key,
            max(1, int(ttl_seconds or _DEFAULT_OWNER_TTL_SECONDS)),
            json.dumps(lease.to_dict(), ensure_ascii=False),
        )
        return lease

    async def refresh_owner(
        self,
        *,
        listener_id: str,
        turn_id: str,
        bundle_id: str = "",
        ttl_seconds: int = _DEFAULT_OWNER_TTL_SECONDS,
    ) -> TimelineOwnerLease:
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        existing = await self.get_owner()
        started_at = existing.started_at if existing and existing.listener_id == listener_id else now_iso
        lease = TimelineOwnerLease(
            turn_id=turn_id or "",
            bundle_id=bundle_id or (existing.bundle_id if existing else ""),
            instance_id=os.getenv("INSTANCE_ID", "unknown"),
            process_id=os.getpid(),
            listener_id=listener_id or (existing.listener_id if existing else ""),
            started_at=started_at,
            updated_at=now_iso,
        )
        await self.redis.setex(
            self.owner_key,
            max(1, int(ttl_seconds or _DEFAULT_OWNER_TTL_SECONDS)),
            json.dumps(lease.to_dict(), ensure_ascii=False),
        )
        return lease

    async def release_owner(self, *, listener_id: str) -> None:
        existing = await self.get_owner()
        if existing is None:
            return
        if listener_id and existing.listener_id and existing.listener_id != listener_id:
            return
        await self.redis.delete(self.owner_key)

    async def _read_event_ref(self, raw: Any) -> Optional[ConversationExternalEvent]:
        stream_id = None
        fields: Any = raw
        if isinstance(raw, (tuple, list)) and len(raw) == 2:
            stream_id, fields = raw[0], raw[1]
        if isinstance(stream_id, bytes):
            stream_id = stream_id.decode("utf-8")
        if isinstance(fields, bytes):
            fields = fields.decode("utf-8")
        if isinstance(fields, str):
            stripped = fields.strip()
            if stripped.startswith("{"):
                item = ConversationExternalEvent.from_any(stripped)
                if item.stream_id is None and stream_id:
                    item.stream_id = str(stream_id)
                return item
            item = await self.get_event(stripped)
            if item is not None and item.stream_id is None and stream_id:
                item.stream_id = str(stream_id)
            return item
        if isinstance(fields, dict):
            message_id = None
            for key in ("message_id", b"message_id"):
                value = fields.get(key)
                if value is not None:
                    message_id = value.decode("utf-8") if isinstance(value, bytes) else str(value)
                    break
            if message_id:
                item = await self.get_event(message_id)
                if item is not None and item.stream_id is None and stream_id:
                    item.stream_id = str(stream_id)
                return item
            item = ConversationExternalEvent.from_any(fields)
            if item.stream_id is None and stream_id:
                item.stream_id = str(stream_id)
            return item
        return None

    async def _write_event(self, event: ConversationExternalEvent) -> None:
        payload = json.dumps(event.to_dict(), ensure_ascii=False)
        setter = getattr(self.redis, "set", None)
        if callable(setter):
            try:
                await setter(self.event_key(event.message_id), payload)
                return
            except TypeError:
                pass
        await self.redis.setex(self.event_key(event.message_id), 315360000, payload)

    async def _claim_event(self, message_id: str, *, claimant_id: str, ttl_seconds: int) -> bool:
        setter = getattr(self.redis, "set", None)
        if callable(setter):
            try:
                res = await setter(
                    self.claim_key(message_id),
                    str(claimant_id or ""),
                    ex=max(1, int(ttl_seconds or 120)),
                    nx=True,
                )
                return bool(res)
            except TypeError:
                pass
        raw = await self.redis.get(self.claim_key(message_id))
        if raw is not None:
            return False
        await self.redis.setex(
            self.claim_key(message_id),
            max(1, int(ttl_seconds or 120)),
            str(claimant_id or ""),
        )
        return True

    async def _get_promotion_cursor(self) -> str:
        raw = await self.redis.get(self.promotion_cursor_key)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return str(raw or "").strip()

    async def _advance_promotion_cursor(self, stream_id: str) -> None:
        stream_id = str(stream_id or "").strip()
        if not stream_id:
            return
        current = await self._get_promotion_cursor()
        if current and self._compare_stream_ids(stream_id, current) <= 0:
            return
        setter = getattr(self.redis, "set", None)
        if callable(setter):
            try:
                await setter(self.promotion_cursor_key, stream_id)
                return
            except TypeError:
                pass
        await self.redis.setex(self.promotion_cursor_key, 315360000, stream_id)

    async def _append_to_stream(self, event: ConversationExternalEvent) -> str:
        fields = {"message_id": str(event.message_id or "")}
        xadd = getattr(self.redis, "xadd", None)
        if callable(xadd):
            stream_id = await xadd(self.log_key, fields)
            if isinstance(stream_id, bytes):
                stream_id = stream_id.decode("utf-8")
            return str(stream_id or "")
        await self.redis.rpush(self.log_key, event.message_id)
        return ""

    async def _stream_read_all(self) -> List[Any]:
        xrange = getattr(self.redis, "xrange", None)
        if callable(xrange):
            return list(await xrange(self.log_key, min="-", max="+"))
        return list(await self.redis.lrange(self.log_key, 0, -1))

    async def _stream_read_since(self, cursor: str | int | None, *, limit: Optional[int] = None) -> List[Any]:
        xrange = getattr(self.redis, "xrange", None)
        if callable(xrange):
            start = "-"
            if cursor not in (None, "", 0, "0"):
                if isinstance(cursor, str) and "-" in cursor:
                    start = f"({cursor}"
                else:
                    start = "-"
            items = list(await xrange(self.log_key, min=start, max="+", count=limit))
            if isinstance(cursor, int) and cursor > 0:
                out: List[Any] = []
                for raw in items:
                    item = await self._read_event_ref(raw)
                    if item is None:
                        continue
                    if int(item.sequence or 0) <= int(cursor):
                        continue
                    out.append(raw)
                    if limit is not None and len(out) >= int(limit):
                        break
                return out
            return items
        raw_items = await self.redis.lrange(self.log_key, 0, -1)
        if isinstance(cursor, int):
            seq_floor = int(cursor or 0)
            out = []
            for raw in raw_items or []:
                item = await self._read_event_ref(raw)
                if item is None or int(item.sequence or 0) <= seq_floor:
                    continue
                out.append(raw)
                if limit is not None and len(out) >= int(limit):
                    break
            return out
        return list(raw_items or [])

    async def _stream_wait_for_after(self, cursor: str | int | None, *, block_ms: int, limit: Optional[int] = None) -> List[Any]:
        xread = getattr(self.redis, "xread", None)
        if callable(xread):
            if isinstance(cursor, str) and "-" in cursor:
                start_id = cursor
            elif cursor not in (None, "", 0, "0"):
                return await self._stream_read_since(cursor, limit=limit)
            else:
                start_id = "$"
            response = await xread(
                {self.log_key: start_id},
                count=limit,
                block=max(1, int(block_ms or 1)),
            )
            return self._flatten_xread_response(response)
        sleep_seconds = max(0.05, float(block_ms or 0) / 1000.0)
        await _sleep_async(sleep_seconds)
        return await self._stream_read_since(cursor, limit=limit)

    def _flatten_xread_response(self, response: Any) -> List[Any]:
        if not response:
            return []
        out: List[Any] = []
        if isinstance(response, dict):
            for items in response.values():
                if isinstance(items, list):
                    out.extend(items)
            return out
        if isinstance(response, list):
            for entry in response:
                if isinstance(entry, (tuple, list)) and len(entry) == 2:
                    items = entry[1]
                    if isinstance(items, list):
                        out.extend(items)
            return out
        return []

    def _compare_stream_ids(self, left: str, right: str) -> int:
        def _parts(value: str) -> tuple[int, int]:
            try:
                first, second = str(value or "").split("-", 1)
                return int(first), int(second)
            except Exception:
                return 0, 0

        l = _parts(left)
        r = _parts(right)
        if l < r:
            return -1
        if l > r:
            return 1
        return 0


async def _sleep_async(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


def build_conversation_external_event_source(*, redis, tenant: str, project: str, conversation_id: str) -> RedisConversationExternalEventSource:
    return RedisConversationExternalEventSource(
        redis=redis,
        tenant=tenant,
        project=project,
        conversation_id=conversation_id,
    )
