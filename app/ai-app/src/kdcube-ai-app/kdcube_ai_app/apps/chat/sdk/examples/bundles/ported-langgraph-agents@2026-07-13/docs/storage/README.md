---
id: kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/ported-langgraph-agents@2026-07-13/docs/storage/README.md
title: "Ported LangGraph Agents Storage Map"
summary: "The non-hosted → hosted storage transition for ported-langgraph-agents@2026-07-13: each of the two vendored agents' own Postgres store (memory/KB/checkpointer) is routed onto KDCube's SHARED Postgres (pg_pool) in its OWN per-agent schema, so each agent is stateless AND the two agents' state never mixes."
status: active
tags: ["ported-langgraph-agents", "storage", "postgres", "pgvector", "langgraph", "checkpointer", "pg_pool", "stateless", "multi-agent", "platform"]
---

# Ported LangGraph Agents Storage Map

Each standalone agent (the "before") keeps every mutable byte in its OWN Postgres,
on one machine. Hosted by KDCube, the SAME process serves many users across many
tenants concurrently, hosts BOTH agents, and any worker may serve any turn. So the
storage transition is: route each agent's own store onto KDCube's SHARED Postgres
(`self.pg_pool`'s database), in its OWN **per-agent** SCHEMA, keyed per
(user, conversation). Each agent then holds nothing per-turn in-process — it is
stateless and distributed-safe, and the two agents' state can never mix.

The graph LOGIC is unchanged. Only the DB EDGE moves: which Postgres, and which
**per-agent** schema, the same nodes + checkpointer connect through.

## Per-agent schemas

```text
  lg-solution  ->  ported_langgraph_agents__lg_solution   (memory + KB + checkpointer)
  lg-react  ->  ported_langgraph_agents__lg_react   (checkpointer)
```

`platform/pg_target.agent_schema(agent_id)` computes the name (hyphens fold to
underscores for a libpq-safe identifier). Two mechanisms keep the agents isolated:
the per-agent schema (physical table separation) AND the identity gate folding
`agent_id` into `user_id`/`thread_id` (key-level separation) — so even in a shared
schema the keys would not collide.

## Before → after (by data kind)

| Data kind | Local (before — poc / standalone) | Hosted (KDCube backend) |
| --- | --- | --- |
| lg-solution working/episodic recall — pgvector `memories` | its own Postgres (`DATABASE_URL`) | `pg_pool`, schema `ported_langgraph_agents__lg_solution` |
| lg-solution knowledge base — seeded `kb_documents` | its own Postgres (`DATABASE_URL`) | `pg_pool`, schema `ported_langgraph_agents__lg_solution` |
| lg-solution LangGraph checkpointer | its own Postgres (`DATABASE_URL`) | `pg_pool`, schema `ported_langgraph_agents__lg_solution` |
| lg-react LangGraph checkpointer | its own Postgres (`DATABASE_URL`) | `pg_pool`, schema `ported_langgraph_agents__lg_react` |
| Conversation record — framework-neutral turn log (`final_answer`) | none | the platform conversation record (option A — already mapped, either agent) |
| Ephemeral cache | in-process | KDCube KV cache (`kv_cache`, from the base entrypoint) |

The compiled graphs and held checkpointer connections stay process-local — a
per-PROCESS template and a connection per agent, never per-turn state.

## The injection point (the whole selection)

There is no runtime toggle. The ONLY selection is whether the bundle hands an
agent a KDCube Postgres connection:

```text
  pg_pool present  ->  KDCube shared Postgres DSN + the AGENT'S schema   (HOSTED)
  else             ->  the agent's own DATABASE_URL                      (LOCAL / poc)
  DB unreachable   ->  empty recall + a MemorySaver checkpointer         (OFFLINE)
```

`entrypoint._hosted_database_url(own_url, schema)` calls
`pg_target.resolve_solution_pg(pg_pool, own_url, schema)` per agent, ensures the
schema, and hands that agent a `Config` whose `database_url` targets the resolved
store; `_open_checkpointer(agent_id, url)` opens on the same DSN. Memory and the
checkpointer flip together, per agent. The fallback chain keeps an offline /
bare-local run working.

**Driver bridge.** KDCube's `pg_pool` is an *asyncpg* pool; the agents and
LangGraph use *psycopg v3*. So the pool object is never handed across the driver
boundary. `platform/pg_target.py` derives a psycopg/libpq DSN from the SAME
platform settings `get_pg_pool()` builds the pool from (`get_settings()` `PG*`
fields + SSL). The pool's PRESENCE is the hosted signal; the settings are the
durable connection bridge.

**Schema isolation.** The DSN carries a libpq `options=-c search_path=<schema>,public`
(see `solution/lg_solution/_pg.with_search_path`), so every store — the pgvector
`memories`, the native `langgraph_store`, `kb_documents`, and the checkpointer
tables — lands in the agent's own schema, isolated from platform tables (`public`)
and from the sibling agent, without touching any SQL. `public` stays on the path so
the shared `vector` extension type still resolves. Each schema is created once
(idempotent) before any node runs DDL.

## Isolation gate

Every store is partitioned by `platform/identity.py`, which folds the ACTIVE
`agent_id` into the keys:

```text
platform state + agent_id        agent key
  tenant + project + AGENT + user  ->  user_id   = "{tenant}:{project}:{agent}:{user}"
  user_id + conversation           ->  thread_id = "{user_id}:{conversation}"
```

The fold into `user_id` makes single-machine agent code safe for many concurrent
users AND keeps the two agents' per-user stores apart: the same raw user id under
lg-solution and lg-react resolves to different keys. Anonymous callers fall back
to `fingerprint`, then `"anonymous"`.

## The map-by-data-kind rule

- **A conversation / turn log** → the platform **conversation record** (option A).
  Both agents map here.
- **Durable user facts / preferences** → the **`mem` named service** (the deeper
  option). Neither agent uses it: lg-solution's `memories` are its own working
  recall, not durable cross-app user facts.
- **An agent's OWN working store** (its private recall, KB, framework checkpoints)
  → the agent's **OWN tables on KDCube's shared Postgres (`pg_pool`)** in its own
  per-agent schema. This is where each agent's memory/KB/checkpointer go.

## Ownership matrix

| Object | Owner | Storage (hosted) | Keyed by | Notes |
| --- | --- | --- | --- | --- |
| lg-solution working/episodic memory (pluggable backend) | the agent | `pg_pool`, schema `..._lg_solution` (`custom` pgvector `memories` \| `langgraph_store` native store) | `user_id = "{tenant}:{project}:lg-solution:{user}"` | The agent's OWN working store (not `mem`). Backend by `LG_MEMORY_BACKEND`. Unreachable DB → empty recall. |
| lg-solution knowledge base (`kb_documents`) | the agent | `pg_pool`, schema `..._lg_solution` | shared across users (dedup by title) | Seeded corpus; rides the same schema. |
| lg-solution / lg-react checkpoints | the agent (framework) | `pg_pool`, the agent's schema | `thread_id` (scoped by user + agent) | Unreachable DB → an in-memory `MemorySaver`. |
| Compiled graphs + held checkpointer connections | this app (process-local) | process memory | per process, per agent | Per-PROCESS templates + connections, not per-turn state. |
| Conversation record (turn log, `final_answer`) | the platform | platform conversation store | platform conversation id | Framework-neutral; the app only sets `state["final_answer"]`. |
| User agent selection (Capabilities model pick) | the platform | KDCube control-plane Postgres (`UserAgentSelectionStore`) | `(user_id, bundle_id, agent_id, conversation_id)` | Read-through; resolved per turn for the ACTIVE agent. |
| Economics / budget state | the platform | KDCube control-plane Postgres + Redis | tenant/project/user subject | Read-through; seeded at deploy from `economics.yaml`. |

## Statelessness invariant

Nothing per-turn lives in-process. Everything held on the entrypoint instance is a
per-PROCESS template or a connection — the compiled graphs (per agent; stateless,
keyed per turn by `thread_id` in `run_config`) and the held checkpointer
connections. Every mutable byte is in shared Postgres keyed by (agent, user,
conversation). So **any processor worker can serve any turn for either agent**
(regression-tested: `tests/test_storage_pg_target.py`, `tests/test_dispatch.py`).

## Secrets

Two deployment secrets (see
[../../config/bundles.secrets.template.yaml](../../config/bundles.secrets.template.yaml)):

- `OPENAI_API_KEY` — the agents' model. Absent → the deterministic offline stub.
- `DATABASE_URL` — the agents' own Postgres, used ONLY on the standalone path
  (no `pg_pool`). Hosted, each agent's store lives on KDCube's shared Postgres via
  `pg_pool` + platform `POSTGRES_*` settings. Absent / unreachable on the local
  path → empty retrieval + an in-memory checkpointer.

No user credentials and no user state belong in any descriptor template.

## Retention, backup, cleanup

Hosted, each agent's store lives in KDCube's shared Postgres under its own bundle
schema, so it follows the platform's database operations (backup, vacuum,
retention) scoped to that schema. On the standalone path each agent's own Postgres
remains the operational concern. The conversation record follows the platform's own
retention policy.
