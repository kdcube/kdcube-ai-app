"""Small shared pgvector helpers — pure, driver-light.

Two kinds of helper live here, split by which store edge uses them:

  - `to_vector_literal` — formats a Python float list as a pgvector text literal.
    The memory + KB stores bind it as a plain text parameter under an explicit
    ``::vector`` cast, so they drive KDCube's SHARED asyncpg pool directly (the
    `SemanticMemory`/`KnowledgeBase` constructors take that pool) — no psycopg.
  - `with_search_path` — a pure string transform that appends a libpq
    ``options=-c search_path=<schema>,public`` to a DSN. Only the LangGraph
    checkpointer (`AsyncPostgresSaver`) and the optional `langgraph_store` backend
    (`AsyncPostgresStore`) connect through such a DSN; both genuinely require
    psycopg v3, which is their own dependency — this module never imports it.

Nothing here opens a connection or imports a driver, so importing the store
modules (and therefore the graph) never requires psycopg/pgvector or a live DB.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit


@dataclass(frozen=True)
class StorageScope:
    """The row-level scope every memory/KB row is tagged with — carried as DATA,
    not baked into a schema name.

    The store lives in ONE per-tenant/project schema (``kdcube_{tenant}_{project}``,
    shared with `conv_index`/`UserMemoryStore`) and every table is bundle-prefixed;
    partitioning is by these COLUMNS. ``agent_id`` keeps lg-solution's rows separate
    from lg-react's inside that one shared table — the per-agent isolation that used
    to be a per-agent schema is now a `WHERE agent_id = …` column filter."""

    tenant: str
    project: str
    bundle_id: str
    agent_id: str


def with_search_path(database_url: str, schema: str) -> str:
    """Return `database_url` carrying a libpq ``options=-c search_path=<schema>,public``
    parameter.

    Only the psycopg-backed stores connect through the result — LangGraph's
    `AsyncPostgresSaver` (checkpointer) and `AsyncPostgresStore` (the optional
    ``langgraph_store`` memory backend) opened via `from_conn_string`. They then
    create and read their tables inside `schema`, so those framework-owned stores
    live in ONE shared Postgres (KDCube's `pg_pool` database) isolated from other
    tables, without touching any SQL. `public` stays on the path so the shared
    `vector` extension type still resolves. The schema must already exist (the
    entrypoint creates it via the asyncpg pool before the checkpointer opens).
    A pure string transform: no DB, no driver import.
    """
    parts = urlsplit(database_url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q["options"] = f"-c search_path={schema},public"
    # quote_via=quote (not the default quote_plus): libpq URIs use RFC-3986
    # percent-encoding, so a space must be %20 — a '+' would be read literally
    # and break the options string.
    query = urlencode(q, quote_via=quote)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def to_vector_literal(vec: List[float]) -> str:
    """pgvector text literal, e.g. '[0.1,0.2,...]'. Works regardless of whether
    numpy is present, and is accepted by a `vector` column cast — asyncpg binds it
    as a text parameter that the query's explicit ``::vector`` cast converts (the
    same pattern KDCube's `conv_index` uses via `convert_embedding_to_string`)."""
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"
