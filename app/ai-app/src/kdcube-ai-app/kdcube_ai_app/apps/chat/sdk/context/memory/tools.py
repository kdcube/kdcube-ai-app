from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, Sequence

from .models import MemoryScope, MemorySearchRequest, MemorySignal, normalize_scope_filter, normalize_terms
from .store import UserMemoryStore

try:
    from semantic_kernel.functions import kernel_function
except Exception:  # pragma: no cover - semantic-kernel compatibility fallback
    try:
        from semantic_kernel.utils.function_decorator import kernel_function
    except Exception:  # pragma: no cover
        def kernel_function(*_args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
                return fn

            return _decorator


ScopeProvider = Callable[[], Dict[str, Any]]
StoreFactory = Callable[[Dict[str, Any]], UserMemoryStore]
Embedder = Callable[[Sequence[str]], Awaitable[Sequence[Sequence[float]]]]


def _ok(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, **payload}


def _error(code: str, message: str) -> Dict[str, Any]:
    return {"ok": False, "error": code, "message": message}


def _bool_filter(value: str) -> Optional[bool]:
    normalized = str(value or "").strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return None


def _scope_from_dict(raw: Dict[str, Any]) -> MemoryScope:
    return MemoryScope(
        tenant=str(raw.get("tenant") or raw.get("TENANT") or "default"),
        project=str(raw.get("project") or raw.get("PROJECT") or "default"),
        user_id=str(raw.get("user_id") or raw.get("owner_user_id") or "anonymous"),
        bundle_id=str(raw.get("bundle_id") or raw.get("app_bundle_id") or ""),
    ).normalized()


def _source_from_scope(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "conversation_id": str(raw.get("conversation_id") or ""),
        "turn_id": str(raw.get("turn_id") or ""),
        "bundle_id": str(raw.get("bundle_id") or raw.get("app_bundle_id") or ""),
    }


def _source_for_action(raw: Dict[str, Any], *, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    scope = _scope_from_dict(raw)
    source = _source_from_scope(raw)
    digest = hashlib.sha256(
        "\n".join([
            scope.tenant,
            scope.project,
            scope.user_id,
            scope.bundle_id,
            source.get("conversation_id", ""),
            source.get("turn_id", ""),
            action,
            json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str),
        ]).encode("utf-8")
    ).hexdigest()
    source["idempotency_key"] = f"memory_tool:{action}:{digest}"
    return source


def _record_payload(result: Any) -> Dict[str, Any]:
    nested_memory = getattr(result, "memory", None)
    memory = nested_memory if hasattr(nested_memory, "id") and hasattr(nested_memory, "scope") else result
    payload = {
        "id": memory.id,
        "scope": {
            "tenant": memory.scope.tenant,
            "project": memory.scope.project,
            "user_id": memory.scope.user_id,
            "bundle_id": memory.scope.bundle_id,
        },
        "bundle_id": memory.scope.bundle_id,
        "memory": memory.memory,
        "context": memory.context,
        "kind": memory.kind,
        "status": memory.status,
        "visibility": memory.visibility,
        "labels": list(memory.labels),
        "keywords": list(memory.keywords),
        "tier": memory.tier,
        "pinned": bool(getattr(memory, "pinned", False)),
        "confidence_score": memory.confidence_score,
        "importance_score": memory.importance_score,
        "freshness_score": memory.freshness_score,
        "salience_score": memory.salience_score,
        "confirmation_rate": memory.confirmation_rate,
        "evidence_count": memory.evidence_count,
        "update_count": memory.update_count,
        "confirmation_count": memory.confirmation_count,
        "contradiction_count": memory.contradiction_count,
        "created_at": memory.created_at.isoformat(),
        "updated_at": memory.updated_at.isoformat(),
        "last_event_at": memory.last_event_at.isoformat(),
        "revision": memory.revision,
    }
    if hasattr(result, "score"):
        payload["score"] = result.score
        payload["score_breakdown"] = dict(result.score_breakdown)
    return payload


def _event_payload(event: Any) -> Dict[str, Any]:
    return {
        "id": event.id,
        "memory_id": event.memory_id,
        "bundle_id": event.scope.bundle_id,
        "event_type": event.event_type,
        "signal_text": event.signal_text,
        "context": event.context,
        "originator": event.originator,
        "confidence": event.confidence,
        "importance": event.importance,
        "labels": list(event.labels),
        "keywords": list(event.keywords),
        "created_at": event.created_at.isoformat(),
    }


@dataclass
class UserMemoryToolConfig:
    allow_write: bool = True
    ensure_schema_on_first_use: bool = False
    default_limit: int = 8
    default_scope_filter: str = "current_bundle"
    embedding_enabled: bool = True
    embedding_timeout_seconds: float = 3.0
    embedding_model: str = ""


class UserMemoryTools:
    """Reusable bundle tools for SDK cross-conversation memory.

    The bundle supplies a scope provider and optionally a store factory.  This
    keeps auth/runtime ownership outside the tool while avoiding copy/paste
    memory tools in every bundle.
    """

    def __init__(
        self,
        *,
        scope_provider: ScopeProvider,
        store_factory: StoreFactory | None = None,
        embedder: Embedder | None = None,
        config: UserMemoryToolConfig | None = None,
    ):
        self._scope_provider = scope_provider
        self._store_factory = store_factory or self._default_store_factory
        self._embedder = embedder
        self._config = config or UserMemoryToolConfig()
        self._schema_ready = False

    def _default_store_factory(self, raw_scope: Dict[str, Any]) -> UserMemoryStore:
        pg_pool = raw_scope.get("pg_pool")
        app_state = raw_scope.get("app_state")
        if pg_pool is None and app_state is not None:
            pg_pool = getattr(app_state, "pg_pool", None)
        if pg_pool is None:
            raise RuntimeError("memory tools require pg_pool in scope or a custom store_factory")
        scope = _scope_from_dict(raw_scope)
        return UserMemoryStore(pg_pool=pg_pool, tenant=scope.tenant, project=scope.project)

    async def _store_and_scope(self) -> tuple[UserMemoryStore, MemoryScope, Dict[str, Any]]:
        raw = self._scope_provider()
        store = self._store_factory(raw)
        if self._config.ensure_schema_on_first_use and not self._schema_ready:
            await store.ensure_schema()
            self._schema_ready = True
        return store, _scope_from_dict(raw), raw

    async def _embed_one(self, text: str) -> Optional[Sequence[float]]:
        if not self._config.embedding_enabled or self._embedder is None:
            return None
        value = str(text or "").strip()
        if not value:
            return None
        try:
            result = await asyncio.wait_for(
                self._embedder([value]),
                timeout=max(0.1, float(self._config.embedding_timeout_seconds or 3.0)),
            )
            if not result:
                return None
            return result[0]
        except Exception:
            return None

    @kernel_function(
        name="search_memory",
        description=(
            "Search durable cross-conversation user memory. Supports hybrid, recent, recent_created, "
            "recent_events, important, confirmed, and hotset modes."
        ),
    )
    async def search_memory(
        self,
        query: str = "",
        mode: str = "hybrid",
        labels: str = "",
        keywords: str = "",
        kind: str = "",
        status: str = "active",
        visible_to_user: str = "",
        scope_filter: str = "",
        limit: int = 8,
    ) -> Dict[str, Any]:
        try:
            store, scope, _raw = await self._store_and_scope()
            mode_value = mode if mode else "hybrid"
            query_embedding = None
            if mode_value == "hybrid":
                query_embedding = await self._embed_one(query)
            rows = await store.search(
                MemorySearchRequest(
                    scope=scope,
                    query=query,
                    mode=mode_value,
                    labels=normalize_terms(labels),
                    keywords=normalize_terms(keywords),
                    kind=kind,
                    status=status or "active",
                    visible_to_user=_bool_filter(visible_to_user),
                    scope_filter=normalize_scope_filter(scope_filter or self._config.default_scope_filter),
                    limit=limit or self._config.default_limit,
                    query_embedding=query_embedding,
                )
            )
            if mode == "recent_events":
                return _ok({"events": [_event_payload(row) for row in rows], "count": len(rows)})
            return _ok({"memories": [_record_payload(row) for row in rows], "count": len(rows)})
        except Exception as exc:
            return _error("search_memory_failed", str(exc))

    @kernel_function(name="recent_memories", description="Return the last N durable user memories.")
    async def recent_memories(
        self,
        limit: int = 10,
        created: str = "",
        visible_to_user: str = "",
        scope_filter: str = "",
    ) -> Dict[str, Any]:
        try:
            store, scope, _raw = await self._store_and_scope()
            rows = await store.search(
                MemorySearchRequest(
                    scope=scope,
                    mode="recent_created" if bool(_bool_filter(created)) else "recent",
                    status="any",
                    visible_to_user=_bool_filter(visible_to_user),
                    scope_filter=normalize_scope_filter(scope_filter or self._config.default_scope_filter),
                    limit=limit,
                )
            )
            return _ok({"memories": [_record_payload(row) for row in rows], "count": len(rows)})
        except Exception as exc:
            return _error("recent_memories_failed", str(exc))

    @kernel_function(
        name="record_memory",
        description=(
            "Create or update durable user memory from a durable signal. Use only after searching for "
            "existing memory; prefer match_memory_id when updating a known row. "
            "The memory text must be compact trigger first + rule. Context is only why/provenance/examples."
        ),
    )
    async def record_memory(
        self,
        memory: str,
        context: str = "",
        kind: str = "fact",
        event_type: str = "agent_observation",
        originator: str = "agent",
        labels: str = "",
        keywords: str = "",
        visibility: str = "user",
        confidence: float = 0.5,
        importance: float = 0.5,
        match_memory_id: str = "",
    ) -> Dict[str, Any]:
        del originator
        if not self._config.allow_write:
            return _error("memory_write_disabled", "This memory tool instance is read-only")
        try:
            store, scope, raw = await self._store_and_scope()
            embedding = await self._embed_one("\n".join(part for part in [memory, context] if str(part).strip()))
            labels_list = normalize_terms(labels)
            keywords_list = normalize_terms(keywords)
            payload = {
                "memory": memory,
                "context": context,
                "kind": kind,
                "event_type": event_type,
                "labels": labels_list,
                "keywords": keywords_list,
                "visibility": visibility,
                "match_memory_id": match_memory_id,
            }
            record = await store.record_signal(
                scope=scope,
                match_memory_id=match_memory_id,
                require_match=bool(match_memory_id),
                signal=MemorySignal(
                    memory=memory,
                    context=context,
                    kind=kind,
                    event_type=event_type,
                    originator=str(raw.get("originator") or "agent"),
                    labels=labels_list,
                    keywords=keywords_list,
                    visibility=visibility,
                    confidence=confidence,
                    importance=importance,
                    embedding=embedding,
                    embedding_model=self._config.embedding_model,
                    source=_source_for_action(raw, action="record", payload=payload),
                ),
            )
            return _ok({"memory": _record_payload(record)})
        except Exception as exc:
            return _error("record_memory_failed", str(exc))

    @kernel_function(name="confirm_memory", description="Confirm an existing durable memory by id.")
    async def confirm_memory(
        self,
        memory_id: str,
        note: str = "confirmed",
        originator: str = "user",
        importance: float = 0.7,
    ) -> Dict[str, Any]:
        del originator
        if not self._config.allow_write:
            return _error("memory_write_disabled", "This memory tool instance is read-only")
        try:
            store, scope, raw = await self._store_and_scope()
            record = await store.confirm_memory(
                scope=scope,
                memory_id=memory_id,
                note=note,
                originator=str(raw.get("originator") or "agent"),
                importance=importance,
                source=_source_for_action(raw, action="confirm", payload={"memory_id": memory_id, "note": note}),
            )
            if record is None:
                return _error("memory_not_found", f"Memory {memory_id!r} was not found")
            return _ok({"memory": _record_payload(record)})
        except Exception as exc:
            return _error("confirm_memory_failed", str(exc))

    @kernel_function(name="retire_memory", description="Retire an existing durable memory by id.")
    async def retire_memory(
        self,
        memory_id: str,
        reason: str = "retired",
        originator: str = "user",
    ) -> Dict[str, Any]:
        del originator
        if not self._config.allow_write:
            return _error("memory_write_disabled", "This memory tool instance is read-only")
        try:
            store, scope, raw = await self._store_and_scope()
            record = await store.retire_memory(
                scope=scope,
                memory_id=memory_id,
                reason=reason,
                originator=str(raw.get("originator") or "agent"),
                source=_source_for_action(raw, action="retire", payload={"memory_id": memory_id, "reason": reason}),
            )
            if record is None:
                return _error("memory_not_found", f"Memory {memory_id!r} was not found")
            return _ok({"memory": _record_payload(record)})
        except Exception as exc:
            return _error("retire_memory_failed", str(exc))


def make_user_memory_tools(
    *,
    scope_provider: ScopeProvider,
    store_factory: StoreFactory | None = None,
    embedder: Embedder | None = None,
    allow_write: bool = True,
    ensure_schema_on_first_use: bool = False,
    default_scope_filter: str = "current_bundle",
    embedding_enabled: bool = True,
    embedding_timeout_seconds: float = 3.0,
    embedding_model: str = "",
) -> UserMemoryTools:
    return UserMemoryTools(
        scope_provider=scope_provider,
        store_factory=store_factory,
        embedder=embedder,
        config=UserMemoryToolConfig(
            allow_write=allow_write,
            ensure_schema_on_first_use=ensure_schema_on_first_use,
            default_scope_filter=default_scope_filter,
            embedding_enabled=embedding_enabled,
            embedding_timeout_seconds=embedding_timeout_seconds,
            embedding_model=embedding_model,
        ),
    )
