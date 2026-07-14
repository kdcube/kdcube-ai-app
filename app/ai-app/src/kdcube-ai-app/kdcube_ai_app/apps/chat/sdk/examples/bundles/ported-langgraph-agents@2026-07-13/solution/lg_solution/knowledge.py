"""A pgvector knowledge base.

`ingest(docs)` upserts documents (dedup by title), `search(query, k)` returns the
top-k by cosine similarity. `seed()` loads a handful of sample docs so a fresh
run can answer something immediately.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Sequence

from ._pg import StorageScope, to_vector_literal
from .config import Config
from .llm import LLMClient

# The bundle-prefixed table NAME inside the shared `kdcube_{tenant}_{project}`
# schema (one schema per tenant/project; rows scoped by columns).
TABLE_KB = "ported_langgraph_agents_kb"


def _kb_table_ref(schema: Optional[str]) -> str:
    """The schema-qualified, quoted `ported_langgraph_agents_kb` reference."""
    return f'"{schema}".{TABLE_KB}' if schema else TABLE_KB


async def ensure_kb_schema(con, schema: Optional[str], embed_dim: int) -> None:
    """Run the KB store's DDL on `con`: the shared `kdcube_{tenant}_{project}` schema
    + the bundle-prefixed `ported_langgraph_agents_kb` table, all `IF NOT EXISTS`,
    never `CREATE EXTENSION` (the platform PostgresSetup job owns the `vector`
    extension).

    Shared across agents — NO `user_id`/`agent_id` filter: provisioned once, every
    agent's rows partition by the scope columns. The single source of the KB DDL,
    called both lazily by `_prepare` (per connection, first use) and up front by
    `ensure_kb_tables` (on_bundle_load) so the KB table exists before any seed."""
    ref = _kb_table_ref(schema)
    if schema:
        await con.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    await con.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ref} (
            id        BIGSERIAL PRIMARY KEY,
            tenant    TEXT NOT NULL,
            project   TEXT NOT NULL,
            bundle_id TEXT NOT NULL,
            agent_id  TEXT NOT NULL,
            title     TEXT NOT NULL,
            text      TEXT NOT NULL,
            embedding vector({embed_dim}) NOT NULL,
            UNIQUE (tenant, project, bundle_id, agent_id, title)
        )
        """
    )


async def ensure_kb_tables(pool, schema: Optional[str], embed_dim: int) -> None:
    """Bundle-level provisioning: acquire one connection from `pool` and ensure the KB
    schema + table exist up front (at bundle load), independent of any agent's first
    turn / KB seed. No-op offline (no pool)."""
    if pool is None:
        return
    async with pool.acquire() as con:
        await ensure_kb_schema(con, schema, embed_dim)


@dataclass
class Doc:
    title: str
    text: str


@dataclass
class KBHit:
    title: str
    text: str
    score: float


# A tiny domain KB so the assistant is useful out of the box.
SEED_DOCS: List[Doc] = [
    Doc(
        "LangGraph checkpointers",
        "LangGraph persists graph state via checkpointers keyed by thread_id. "
        "The Postgres checkpointer stores each step so a conversation can resume "
        "across process restarts. Swap MemorySaver for PostgresSaver to persist.",
    ),
    Doc(
        "pgvector basics",
        "pgvector adds a `vector` column type to Postgres and distance operators. "
        "`<=>` is cosine distance; ORDER BY embedding <=> query gives nearest "
        "neighbours. The `vector` extension is enabled once per database before use.",
    ),
    Doc(
        "Retrieval-augmented generation",
        "RAG retrieves relevant documents for a query and feeds them to the model "
        "as grounding context, reducing hallucination and letting answers cite a "
        "source corpus rather than only model parameters.",
    ),
    Doc(
        "astream_events streaming",
        "graph.astream_events(version='v2') yields typed events: on_chain_start, "
        "on_chat_model_stream (token chunks), on_chain_end. A UI or CLI subscribes "
        "to these to render tokens and node progress as they happen.",
    ),
    Doc(
        "Subagents as sub-graphs",
        "A subagent can be a nested StateGraph the main graph delegates a scoped "
        "sub-question to. It runs its own retrieve/synthesize steps and returns a "
        "compact result, keeping the parent graph's context focused.",
    ),
]


class KnowledgeBase:
    """A pgvector KB on KDCube's SHARED asyncpg pool.

    Drives the injected pool DIRECTLY (`pool.acquire()` -> `con.execute` /
    `con.fetch`) — the same pool `conv_index` uses — so it needs no psycopg. The
    bundle-prefixed `ported_langgraph_agents_kb` table lives in the ONE
    per-tenant/project `schema` (`kdcube_{tenant}_{project}`); rows are scoped by the
    `(tenant, project, bundle_id, agent_id)` COLUMNS, so each agent keeps its own KB
    inside the shared table. Query embeddings bind as text literals under an explicit
    ``::vector`` cast.

    Async so every embedding + DB call runs on the event loop inside the graph's
    `retrieve` node (and the subagent's `research` node), within the turn's bound
    accounting context — the processor loop never blocks and nothing is offloaded
    to an executor thread that would lose the accounting contextvar (the
    previously-flagged unbilled-embedding gap).

    With no pool injected (offline / no shared DB) `search` returns empty and
    `ingest`/`seed` are no-ops, so an offline turn never crashes."""

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
        return _kb_table_ref(self._schema)

    async def ensure_tables(self) -> None:
        """Bundle-level provisioning at load: ensure the shared schema + KB table
        exist independent of any agent's first turn / seed. Idempotent
        (`IF NOT EXISTS`), no-op offline. Marks the store ready."""
        await ensure_kb_tables(self._pool, self._schema, self.config.embed_dim)
        self._ready = True

    async def _prepare(self, con) -> None:
        """Idempotent lazy fallback: ensure the schema + table exist on first use if
        `ensure_tables`/`on_bundle_load` did not already run. The platform
        PostgresSetup job owns the `vector` extension — the bundle never provisions
        it, only `CREATE SCHEMA`/`CREATE TABLE IF NOT EXISTS`."""
        if self._ready:
            return
        await ensure_kb_schema(con, self._schema, self.config.embed_dim)
        self._ready = True

    async def ingest(self, docs: Sequence[Doc]) -> int:
        docs = [d for d in docs if d.text.strip()]
        if not docs or self._pool is None:
            return 0
        vecs = await self.llm.embed([f"{d.title}\n{d.text}" for d in docs])
        s = self._scope
        async with self._pool.acquire() as con:
            await self._prepare(con)
            for d, v in zip(docs, vecs):
                await con.execute(
                    f"""
                    INSERT INTO {self._table()}
                        (tenant, project, bundle_id, agent_id, title, text, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7::vector)
                    ON CONFLICT (tenant, project, bundle_id, agent_id, title) DO UPDATE
                        SET text = EXCLUDED.text, embedding = EXCLUDED.embedding
                    """,
                    s.tenant, s.project, s.bundle_id, s.agent_id,
                    d.title, d.text, to_vector_literal(v),
                )
        return len(docs)

    async def seed(self) -> int:
        """Idempotent: only ingests when this scope's KB is empty."""
        if self._pool is None:
            return 0
        s = self._scope
        async with self._pool.acquire() as con:
            await self._prepare(con)
            count = await con.fetchval(
                f"""
                SELECT COUNT(*) FROM {self._table()}
                WHERE tenant = $1 AND project = $2 AND bundle_id = $3 AND agent_id = $4
                """,
                s.tenant, s.project, s.bundle_id, s.agent_id,
            )
            if count and int(count) > 0:
                return 0
        return await self.ingest(SEED_DOCS)

    async def search(self, query: str, k: int = 4) -> List[KBHit]:
        query = (query or "").strip()
        if not query or self._pool is None:
            return []
        vec = (await self.llm.embed([query]))[0]
        s = self._scope
        async with self._pool.acquire() as con:
            await self._prepare(con)
            rows = await con.fetch(
                f"""
                SELECT title, text, 1 - (embedding <=> $1::vector) AS score
                FROM {self._table()}
                WHERE tenant = $2 AND project = $3 AND bundle_id = $4 AND agent_id = $5
                ORDER BY embedding <=> $1::vector
                LIMIT $6
                """,
                to_vector_literal(vec), s.tenant, s.project, s.bundle_id, s.agent_id, k,
            )
            return [KBHit(title=r["title"], text=r["text"], score=float(r["score"])) for r in rows]
