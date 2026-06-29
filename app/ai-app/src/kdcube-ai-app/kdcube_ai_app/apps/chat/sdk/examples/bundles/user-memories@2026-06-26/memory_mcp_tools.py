"""
FastMCP tool surface for the standalone user-memories bundle.

This module is intentionally small and read-only. The authorization boundary is
not implemented here: the bundle MCP route is guarded by the platform-managed
MCP policy configured at ``surfaces.as_provider.mcp.memories.auth``. By the
time these tools run, the proc bridge has already validated the delegated
credential, required ``memories:read``, and the selected tool grant. This file
only turns that accepted principal into memory-store reads.

The scope factory is supplied by the bundle entrypoint. For delegated external
clients, it resolves to the grantor platform user, not to the integration
identity. The optional ``read_user_ids_factory`` widens reads to the grantor's
Connection Hub identity family when that is available and enabled.
"""

from __future__ import annotations

from typing import Annotated, Any, Awaitable, Callable, Literal, Optional

from pydantic import Field

from kdcube_ai_app.apps.chat.sdk.context.memory import (
    MemoryRecord,
    MemoryScope,
    MemorySearchRequest,
    MemorySearchResult,
    UserMemoryStore,
)


StoreFactory = Callable[[], UserMemoryStore]
ScopeFactory = Callable[[], MemoryScope]
ReadUserIdsFactory = Callable[[MemoryScope], Awaitable[Optional[list[str]]]]
MemoryReadStatus = Literal["active", "weakened", "unsupported", "retired", "merged", "any"]

MAX_SEARCH_LIMIT = 50
DEFAULT_SEARCH_LIMIT = 10
READ_STATUS_FILTERS = ("active", "weakened", "unsupported", "retired", "merged", "any")


def _iso(value: Any) -> str:
    """Serialize store timestamps into stable JSON-friendly strings."""
    try:
        return value.isoformat()
    except Exception:
        return str(value or "")


def _record_payload(record: MemoryRecord, *, score: float | None = None) -> dict[str, Any]:
    """Return the stable public MCP shape for one memory record.

    The payload is explicit on purpose: it avoids leaking internal store fields
    and keeps Claude/external clients on a small, documented read contract.
    """
    data = {
        "id": record.id,
        "user_id": record.scope.user_id,
        "bundle_id": record.scope.bundle_id,
        "memory": record.memory,
        "context": record.context,
        "kind": record.kind,
        "status": record.status,
        "visibility": record.visibility,
        "labels": list(record.labels or []),
        "keywords": list(record.keywords or []),
        "tier": record.tier,
        "pinned": record.pinned,
        "confidence_score": record.confidence_score,
        "importance_score": record.importance_score,
        "salience_score": record.salience_score,
        "created_at": _iso(record.created_at),
        "updated_at": _iso(record.updated_at),
        "last_event_at": _iso(record.last_event_at),
        "revision": record.revision,
    }
    if score is not None:
        data["score"] = score
    return data


def _safe_limit(value: int) -> int:
    """Clamp caller-provided limits so MCP clients cannot request huge scans."""
    try:
        requested = int(value or DEFAULT_SEARCH_LIMIT)
    except Exception:
        requested = DEFAULT_SEARCH_LIMIT
    return max(1, min(requested, MAX_SEARCH_LIMIT))


def _normalized_status(value: str) -> str:
    """Normalize the MCP-facing status filter to a documented value."""
    raw = str(value or "active").strip().lower() or "active"
    return raw if raw in READ_STATUS_FILTERS else "active"


def build_user_memories_mcp_app(
    *,
    name: str,
    store_factory: StoreFactory,
    scope_factory: ScopeFactory,
    read_user_ids_factory: ReadUserIdsFactory,
):
    """Build the read-only FastMCP app for user memory access.

    Parameters:
    - ``store_factory`` returns the memory store bound to the current runtime.
    - ``scope_factory`` returns the effective memory scope for this request. In
      delegated-client calls this is the approving KDCube user from the
      credential envelope.
    - ``read_user_ids_factory`` optionally returns all linked user ids that
      should be included in user-facing reads. If it fails, these tools fall
      back to the single effective user id instead of failing the whole MCP
      call.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise ImportError("mcp server SDK is not installed") from exc

    mcp = FastMCP(name)

    async def _read_user_ids(scope: MemoryScope) -> Optional[list[str]]:
        """Resolve the identity-family read set, with safe single-user fallback."""
        try:
            return await read_user_ids_factory(scope)
        except Exception:
            return None

    @mcp.tool(
        name="memory_search",
        description=(
            "Search the approving user's KDCube memory notes. This is a read-only "
            "delegated tool for external clients such as Claude. Results are scoped "
            "to the grantor user and, when Connection Hub identity-family reads are "
            "available, to the grantor's linked identities."
        ),
    )
    async def _memory_search(
        query: Annotated[
            str,
            Field(
                description=(
                    "Natural-language memory search query. Leave empty to list the "
                    "most recent visible memories for the approving user."
                )
            ),
        ] = "",
        limit: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_SEARCH_LIMIT,
                description=(
                    "Maximum number of memory notes to return. The server clamps "
                    f"this to the range 1..{MAX_SEARCH_LIMIT}."
                ),
            ),
        ] = DEFAULT_SEARCH_LIMIT,
        status: Annotated[
            MemoryReadStatus,
            Field(
                description=(
                    "Memory lifecycle status filter. Allowed values: active, "
                    "weakened, unsupported, retired, merged, any. Use active "
                    "for normal reads. Use any only when the user explicitly asks "
                    "to inspect non-active or historical memories."
                )
            ),
        ] = "active",
    ) -> dict[str, Any]:
        scope = scope_factory().normalized()
        user_ids = await _read_user_ids(scope)
        request = MemorySearchRequest(
            scope=scope,
            query=str(query or "").strip(),
            mode="hybrid" if str(query or "").strip() else "recent",
            status=_normalized_status(status),
            visible_to_user=True,
            include_private=True,
            scope_filter="all_user_memories",
            limit=_safe_limit(limit),
            user_ids=user_ids,
        )
        rows = await store_factory().search(request)
        memories: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, MemorySearchResult):
                memories.append(_record_payload(row.memory, score=row.score))
        return {
            "ok": True,
            "user_id": scope.user_id,
            "memory_user_ids": list(user_ids or [scope.user_id]),
            "count": len(memories),
            "items": memories,
        }

    @mcp.tool(
        name="memory_get",
        description=(
            "Read one KDCube memory note by id. The note is returned only when it "
            "belongs to the approving user's effective memory read scope."
        ),
    )
    async def _memory_get(
        memory_id: Annotated[
            str,
            Field(
                description=(
                    "Exact memory id to read, for example an id returned by "
                    "memory_search. The server does not perform cross-user lookup "
                    "outside the approving user's identity-family scope."
                )
            ),
        ],
    ) -> dict[str, Any]:
        scope = scope_factory().normalized()
        user_ids = await _read_user_ids(scope)
        record = await store_factory().get_memory(
            scope=scope,
            memory_id=str(memory_id or "").strip(),
            visible_to_user=True,
            scope_filter="all_user_memories",
            user_ids=user_ids,
        )
        return {
            "ok": bool(record),
            "user_id": scope.user_id,
            "memory_user_ids": list(user_ids or [scope.user_id]),
            "item": _record_payload(record) if record else None,
        }

    return mcp
