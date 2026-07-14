"""Per-user long-term memory as a PLUGGABLE BACKEND.

A small facts/preferences store: `remember(user_id, text)` writes a note,
`recall(user_id, query, k)` returns the k most relevant notes for that user by
semantic similarity. Scoped by user_id so each person keeps their own memory.

The graph is written against a single `Memory` interface (async `remember` /
`recall`, returning `MemoryHit`), so it never knows which backend is wired.
`LG_MEMORY_BACKEND` selects one of two implementations — the demo's point is to
show both ways of doing LangGraph long-term memory side by side:

  - ``custom``          : a hand-rolled async pgvector table (`SemanticMemory`).
                          The default. The solution owns the schema and SQL, and
                          drives KDCube's SHARED asyncpg pool DIRECTLY (the same
                          pool `conv_index` uses) — no psycopg.
  - ``langgraph_store`` : LangGraph's native store (`StoreMemory`) with a
                          semantic index — `AsyncPostgresStore` from
                          ``langgraph.store.postgres.aio``. The framework owns
                          the schema; we only choose the namespace + index embed.
                          (This backend, like the checkpointer, connects through a
                          psycopg DSN — its own dependency.)

Both are fully async (the bundle runs every embedding + DB call on the event
loop inside a graph node, within the turn's bound accounting context). Both
degrade to empty recall / skipped writes when no pool / no DB — or, for the
store, no `AsyncPostgresStore` — is available, so an offline turn never crashes.
"""
from __future__ import annotations

import abc
import hashlib
import sys
from dataclasses import dataclass
from typing import Any, List, Optional

from ._pg import StorageScope, to_vector_literal
from .config import Config
from .llm import LLMClient

# The bundle-prefixed table NAME inside the shared `kdcube_{tenant}_{project}`
# schema (the canonical KDCube pattern: one schema per tenant/project, tables named
# per bundle, rows scoped by columns).
TABLE_MEMORIES = "ported_langgraph_agents_memories"


def _memories_table_ref(schema: Optional[str]) -> str:
    """The schema-qualified, quoted `ported_langgraph_agents_memories` reference
    (one shared per-tenant/project schema; agents separated by the agent_id
    column, not the schema)."""
    return f'"{schema}".{TABLE_MEMORIES}' if schema else TABLE_MEMORIES


async def ensure_memory_schema(con, schema: Optional[str], embed_dim: int) -> None:
    """Run the memory store's DDL on `con`: the shared `kdcube_{tenant}_{project}`
    schema + the bundle-prefixed `ported_langgraph_agents_memories` table (+ scope
    index), all `IF NOT EXISTS`, never `CREATE EXTENSION` (the platform PostgresSetup
    job owns the `vector` extension).

    Shared across agents — NO `user_id`/`agent_id` filter: the schema and table are
    provisioned once and every agent's rows partition by the scope columns. This is
    the single source of the memory DDL, called both lazily by `_prepare` (per
    connection, first use) and up front by `ensure_memory_tables` (on_bundle_load)."""
    ref = _memories_table_ref(schema)
    if schema:
        await con.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    await con.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ref} (
            id         BIGSERIAL PRIMARY KEY,
            tenant     TEXT NOT NULL,
            project    TEXT NOT NULL,
            bundle_id  TEXT NOT NULL,
            agent_id   TEXT NOT NULL,
            user_id    TEXT NOT NULL,
            text       TEXT NOT NULL,
            embedding  vector({embed_dim}) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    await con.execute(
        f"CREATE INDEX IF NOT EXISTS ported_langgraph_agents_memories_scope_idx "
        f"ON {ref} (tenant, project, bundle_id, agent_id, user_id)"
    )


async def ensure_memory_tables(pool, schema: Optional[str], embed_dim: int) -> None:
    """Bundle-level provisioning: acquire one connection from `pool` and ensure the
    memory schema + table exist up front (at bundle load), independent of any agent's
    first turn. No-op offline (no pool)."""
    if pool is None:
        return
    async with pool.acquire() as con:
        await ensure_memory_schema(con, schema, embed_dim)


@dataclass
class MemoryHit:
    text: str
    score: float  # semantic similarity; higher is closer (0.0 when unranked)


class Memory(abc.ABC):
    """The interface the graph closes over. `graph.py`/`subagent.py` only ever
    call `remember` / `recall` and read `MemoryHit.text` / `.score`, so any
    backend that honors this contract drops in without touching graph logic."""

    @abc.abstractmethod
    async def remember(self, user_id: str, text: str) -> None:
        ...

    @abc.abstractmethod
    async def recall(self, user_id: str, query: str, k: int = 5) -> List[MemoryHit]:
        ...


class SemanticMemory(Memory):
    """Backend ``custom``: a hand-rolled async pgvector table on KDCube's pool.

    Drives KDCube's SHARED asyncpg pool DIRECTLY (`pool.acquire()` -> `con.execute`
    / `con.fetch`) — the same pool `conv_index` uses — so it needs no psycopg. The
    bundle-prefixed `ported_langgraph_agents_memories` table lives in the ONE
    per-tenant/project `schema` (`kdcube_{tenant}_{project}`, shared with
    `conv_index`); rows are scoped by the `(tenant, project, bundle_id, agent_id,
    user_id)` COLUMNS, so the two agents' memories stay apart via `agent_id`, not a
    separate schema. The query embedding is bound as a text literal under an
    explicit ``::vector`` cast.

    Async so every embedding + DB call runs on the event loop inside the graph's
    `retrieve`/`answer` nodes, within the turn's bound accounting context — the
    processor loop never blocks and nothing is offloaded to an executor thread
    that would lose the accounting contextvar.

    With no pool injected (offline / no shared DB) it degrades to empty recall +
    skipped writes, so an offline turn never crashes."""

    def __init__(
        self,
        config: Config,
        llm: LLMClient,
        pool: Any = None,
        schema: Optional[str] = None,
        scope: Optional[StorageScope] = None,
    ) -> None:
        self.config = config
        self.llm = llm
        self._pool = pool
        self._schema = schema
        self._scope = scope or StorageScope(tenant="", project="", bundle_id="", agent_id="")
        self._ready = False

    def _table(self) -> str:
        return _memories_table_ref(self._schema)

    async def ensure_tables(self) -> None:
        """Bundle-level provisioning at load: ensure the shared schema + table exist
        independent of any agent's first turn. Idempotent (`IF NOT EXISTS`), no-op
        offline. Marks the store ready so a later `_prepare` is a cheap no-op."""
        await ensure_memory_tables(self._pool, self._schema, self.config.embed_dim)
        self._ready = True

    async def _prepare(self, con) -> None:
        """Idempotent lazy fallback: ensure the schema + table exist on first use if
        `ensure_tables`/`on_bundle_load` did not already run (offline, a missed load).

        Self-contained on the pool: creates the schema too, so `custom` memory works
        even when the psycopg-dependent checkpointer path could not. The platform
        PostgresSetup job owns the `vector` extension — the bundle never provisions
        it, only `CREATE SCHEMA`/`CREATE TABLE`/`CREATE INDEX IF NOT EXISTS`."""
        if self._ready:
            return
        await ensure_memory_schema(con, self._schema, self.config.embed_dim)
        self._ready = True

    async def remember(self, user_id: str, text: str) -> None:
        text = (text or "").strip()
        if not text or self._pool is None:
            return
        vec = (await self.llm.embed([text]))[0]
        s = self._scope
        async with self._pool.acquire() as con:
            await self._prepare(con)
            await con.execute(
                f"""
                INSERT INTO {self._table()}
                    (tenant, project, bundle_id, agent_id, user_id, text, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7::vector)
                """,
                s.tenant, s.project, s.bundle_id, s.agent_id,
                user_id, text, to_vector_literal(vec),
            )

    async def recall(self, user_id: str, query: str, k: int = 5) -> List[MemoryHit]:
        query = (query or "").strip()
        if not query or self._pool is None:
            return []
        vec = (await self.llm.embed([query]))[0]
        s = self._scope
        async with self._pool.acquire() as con:
            await self._prepare(con)
            rows = await con.fetch(
                f"""
                SELECT text, 1 - (embedding <=> $1::vector) AS score
                FROM {self._table()}
                WHERE tenant = $2 AND project = $3 AND bundle_id = $4
                  AND agent_id = $5 AND user_id = $6
                ORDER BY embedding <=> $1::vector
                LIMIT $7
                """,
                to_vector_literal(vec), s.tenant, s.project, s.bundle_id,
                s.agent_id, user_id, k,
            )
            return [MemoryHit(text=row["text"], score=float(row["score"])) for row in rows]


class StoreMemory(Memory):
    """Backend ``langgraph_store``: LangGraph's native store, semantic-indexed.

    Uses ``AsyncPostgresStore`` (``langgraph.store.postgres.aio``) opened with a
    semantic index whose embed function is `llm.embed` — the SAME accounted async
    embed path the custom backend uses, so index embeddings are billed the same
    way (T2b). Notes are namespaced by ``(user_id,)`` so each user's memory stays
    isolated, matching the custom backend's `WHERE user_id = ...` scoping.

    Mapping:
      - `remember` -> ``await store.aput((user_id,), key, {"text": text})``
        with a stable content-derived key, so re-remembering the same note is
        idempotent rather than duplicating rows.
      - `recall`   -> ``await store.asearch((user_id,), query=..., limit=k)``,
        each `SearchItem` mapped to `MemoryHit(text=item.value["text"],
        score=item.score or 0.0)`.

    Opened lazily on first use in an async context (the store needs an event
    loop). If ``AsyncPostgresStore`` is not importable, or the DB is unreachable,
    it degrades to empty recall / skipped writes exactly like the checkpointer's
    `AsyncPostgresSaver` -> `MemorySaver` fallback — never an import-time or
    turn-time crash."""

    def __init__(self, config: Config, llm: LLMClient) -> None:
        self.config = config
        self.llm = llm
        self._store: Any = None
        self._cm: Any = None  # held so the async store isn't GC'd / closed early
        self._unavailable = False

    async def _get_store(self) -> Optional[Any]:
        if self._store is not None:
            return self._store
        if self._unavailable:
            return None
        try:
            # Lazy import: the Postgres store lives in langgraph-checkpoint-postgres,
            # which is optional here (the processor may ship only base langgraph).
            # A missing package degrades to empty recall, never an import failure.
            from langgraph.store.postgres.aio import AsyncPostgresStore  # lazy
        except Exception as e:  # noqa: BLE001
            self._unavailable = True
            print(f"  [memory:langgraph_store] AsyncPostgresStore unavailable: {e}", file=sys.stderr)
            return None
        try:
            cm = AsyncPostgresStore.from_conn_string(
                self.config.database_url,
                index={
                    "dims": self.config.embed_dim,
                    # Route index embeddings through the accounted async embed
                    # path (guarded facade / models_service / offline stub) —
                    # same billing seam as the custom backend.
                    "embed": self.llm.embed,
                    "fields": ["text"],
                },
            )
            store = await cm.__aenter__()
            await store.setup()
            self._cm = cm
            self._store = store
            return store
        except Exception as e:  # noqa: BLE001 - unreachable DB degrades to empty
            self._unavailable = True
            print(f"  [memory:langgraph_store] store open failed: {e}", file=sys.stderr)
            return None

    @staticmethod
    def _key_for(text: str) -> str:
        # Stable, content-derived key so the same note dedups within a namespace.
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    async def remember(self, user_id: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        store = await self._get_store()
        if store is None:
            return
        await store.aput((user_id,), self._key_for(text), {"text": text})

    async def recall(self, user_id: str, query: str, k: int = 5) -> List[MemoryHit]:
        query = (query or "").strip()
        if not query:
            return []
        store = await self._get_store()
        if store is None:
            return []
        items = await store.asearch((user_id,), query=query, limit=k)
        hits: List[MemoryHit] = []
        for it in items:
            value = getattr(it, "value", None) or {}
            text = str(value.get("text", "")).strip()
            if not text:
                continue
            score = getattr(it, "score", None)
            hits.append(MemoryHit(text=text, score=float(score) if score is not None else 0.0))
        return hits


def build_memory(
    config: Config,
    llm: LLMClient,
    pool: Any = None,
    schema: Optional[str] = None,
    scope: Optional[StorageScope] = None,
) -> Memory:
    """Select the memory backend from ``config.memory_backend``.

    ``custom`` (default) -> `SemanticMemory` on KDCube's shared asyncpg `pool` in
    the per-tenant/project `schema`, rows tagged with `scope`
    (`tenant, project, bundle_id, agent_id`); ``langgraph_store`` -> `StoreMemory`
    (framework store over a psycopg DSN, `config.database_url`). Both wrap the same
    `llm`, so index/query embeddings route through the same accounted path
    regardless of which store persists the notes. An unrecognized value falls back
    to the default so a typo degrades to a working backend."""
    backend = (getattr(config, "memory_backend", "custom") or "custom").strip().lower()
    if backend == "langgraph_store":
        return StoreMemory(config, llm)
    return SemanticMemory(config, llm, pool=pool, schema=schema, scope=scope)
