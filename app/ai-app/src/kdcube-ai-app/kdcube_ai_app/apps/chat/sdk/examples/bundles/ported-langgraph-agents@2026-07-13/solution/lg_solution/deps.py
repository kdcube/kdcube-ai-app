"""Dependency container wiring config -> LLM -> stores -> subagent.

One place that constructs the collaborators the graph nodes close over, so
graph.py and subagent.py stay free of construction logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ._pg import StorageScope
from .config import Config, get_config
from .knowledge import KnowledgeBase
from .llm import LLMClient, get_llm
from .memory import Memory, build_memory


@dataclass
class Deps:
    config: Config
    llm: LLMClient
    memory: Memory
    knowledge: KnowledgeBase


def build_deps(
    config: Config | None = None,
    models_service: Any = None,
    model_role: Optional[str] = None,
    embedding_service: Any = None,
    pg_pool: Any = None,
    schema: Optional[str] = None,
    scope: Optional[StorageScope] = None,
    summary_model_role: Optional[str] = None,
) -> Deps:
    """Wire the graph's collaborators.

    When a KDCube `models_service` is supplied, the LLM client routes chat and
    embeddings through the platform's accounted model service; with it omitted
    (the default) the standalone behavior is unchanged.

    When an `embedding_service` is supplied (the host's economics-guarded search
    facade, or a zero-arg provider returning one), retrieval/memory embeddings
    route through it for per-call budget ENFORCEMENT (T2b). Chat generation stays
    on `models_service`, enforced at the turn level by the economics base
    entrypoint. Omitted (the default) keeps the accounted-only behavior.

    When `pg_pool` (KDCube's SHARED asyncpg pool) + `schema` (the per-tenant/project
    schema) + `scope` (`tenant, project, bundle_id, agent_id`) are supplied, the
    `custom` long-term memory and the KB acquire from that pool DIRECTLY — no
    psycopg — with their bundle-prefixed tables in `schema` and every row tagged by
    `scope` (so the two agents' rows stay apart via the agent_id column). Omitted
    (offline), memory/KB degrade to empty recall + skipped writes.

    When a `summary_model_role` is supplied, the LLM client exposes a summary model
    on that DISTINCT accounted role for the graph's `compact` node (conversation
    compaction); omitted (offline), compaction degrades to a trim.

    The long-term memory backend is chosen by `config.memory_backend`
    (`LG_MEMORY_BACKEND`): `custom` pgvector (on the pool) or `langgraph_store`
    native (a framework store over a psycopg DSN). Both wrap the same `llm`, so
    whichever store persists the notes, its index/query embeddings flow through
    the same accounted (and, when wired, guarded) path.
    """
    config = config or get_config()
    llm = get_llm(
        config,
        models_service=models_service,
        model_role=model_role,
        embedding_service=embedding_service,
        summary_model_role=summary_model_role,
    )
    return Deps(
        config=config,
        llm=llm,
        memory=build_memory(config, llm, pool=pg_pool, schema=schema, scope=scope),
        knowledge=KnowledgeBase(config, llm, pool=pg_pool, schema=schema, scope=scope),
    )
