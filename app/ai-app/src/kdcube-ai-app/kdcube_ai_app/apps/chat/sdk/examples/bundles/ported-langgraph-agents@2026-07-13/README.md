---
id: ported-langgraph-agents@2026-07-13
title: "Ported LangGraph Agents"
summary: "ONE KDCube app that hosts TWO ported LangGraph agents (a research graph and the prebuilt create_react_agent), both vendored unchanged, dispatched by agent_id through a single execute_core. The 'one app, many agents' demonstration."
status: active
tags: ["app", "ported-langgraph-agents", "langgraph", "platform", "port", "chat", "multi-agent", "telegram"]
module: entrypoint
singleton: false
primary_surfaces:
  - "reactive chat turn (surfaces.as_provider.bundle, default_chat) -> execute_core dispatches on agent_id"
  - "telegram webhook (@api route=public, alias=telegram_webhook) -> same execute_core, default agent"
---

# ported-langgraph-agents — ONE app, MANY agents

This app is the **"one app, many agents"** demonstration of the KDCube port
recipe. It hosts **two** standalone LangGraph agents — vendored **unchanged** —
behind a **single `execute_core`** that dispatches on **`agent_id`**:

| agent_id | what it is | shape | stream adapter |
| --- | --- | --- | --- |
| `lg-solution` | the rich research graph (KB retrieval + per-user pgvector memory + a nested subagent) — the "before" is [`../../poc/lg-solution`](../../poc/lg-solution) | linear, with a **dedicated answer node** | `platform/stream_solution.py` |
| `lg-react` | the standard `langgraph.prebuilt.create_react_agent` (plain + MCP tools) — the "before" is [`../../poc/lg-react-agent`](../../poc/lg-react-agent) | ReAct loop, with a **looping agent node** (no answer node) | `platform/stream_prebuilt.py` |

The teaching point: **different agent shapes → different stream adapters, selected
by `agent_id`.** Everything else — identity, storage, capabilities, economics,
the Telegram ingress — is shared platform glue.

## The two sides: `solution/` and `platform/`

```
ported-langgraph-agents@2026-07-13/
  solution/
    lg_solution/       ← the research graph (vendored UNCHANGED from poc/lg-solution)
    lg_prebuilt/       ← the create_react agent (vendored UNCHANGED from poc/lg-react-agent)
  platform/            ← the KDCube integration (shared across both agents):
    identity.py          platform identity + agent_id → each agent's per-user keys
    pg_target.py         storage edge → KDCube pg_pool, a PER-AGENT schema
    stream_solution.py   dedicated-answer-node event stream → comm_ctx
    stream_prebuilt.py   looping-agent-node event stream → comm_ctx
    capabilities.py      per-turn, per-agent model pick
    tools_mcp.py         lg-react's tools seam (plain + MCP)
    telegram.py          the shared ingress (drives the default agent)
  entrypoint.py        ← composition root: execute_core DISPATCHES on agent_id
```

Both `solution/` subpackages never import KDCube; only the `platform/` glue and
`entrypoint.py` know both worlds.

## The dispatcher

`execute_core` is a dispatcher over a per-agent registry:

```text
agent_id (state) ─normalize→ AGENTS[agent_id]  (else the default, lg-solution)
  AgentSpec: build_graph · stream · build_inputs · role · schema
    _ensure_graph(agent_id)   lazy per-agent graph CACHE (built once per process)
    build_inputs(question, ident) → the agent's own input + run_config(thread_id)
    stream(graph, inputs, run_config) → the agent's OWN stream adapter → comm_ctx
  role_models = resolve_turn_role_models(self, state, agent_id)   (the active agent's pick)
  state["final_answer"] = <the streamed answer>
```

Each agent's graph is a **per-process template** built lazily once and reused
across turns/users; per-turn state lives only in shared Postgres keyed by
`thread_id`. So any processor worker can serve any turn for either agent.

## Storage — per-agent isolation

Each agent's own store (lg-solution's memory + KB + checkpointer; lg-react's
checkpointer) is routed onto KDCube's **shared Postgres** (`self.pg_pool`) in its
**own per-agent schema** when hosted:

```text
  lg-solution  ->  schema ported_langgraph_agents__lg_solution
  lg-react  ->  schema ported_langgraph_agents__lg_react
```

Combined with the identity gate folding `agent_id` into the per-user key, the two
agents' state can **never mix**. Standalone (no `pg_pool`) each keeps its own
`DATABASE_URL`; unreachable → empty recall + an in-memory checkpointer. Full map:
[docs/storage/README.md](docs/storage/README.md).

## Surfaces

**Two** ingresses drive the **same** `execute_core`:

1. **the reactive chat turn** (`surfaces.as_provider.bundle`, `default_chat: true`)
   — each user message dispatches on `agent_id` and streams the chosen agent's
   answer back;
2. **the Telegram Bot API webhook** (`@api(route="public", alias="telegram_webhook")`)
   — a Telegram message drives the same turn for the **default agent** and the
   answer is delivered back over the Bot API (all protocol mechanics reused from
   the Telegram SDK; the bundle-side wiring is the thin `platform/telegram.py`).

No MCP server, widget, Data Bus handler, cron, or background job. See
[interface/README.md](interface/README.md),
[interface/ported-langgraph-agents.openapi.yaml](interface/ported-langgraph-agents.openapi.yaml),
and the operator steps in
[docs/integrations/admin-integrational-homework.md](docs/integrations/admin-integrational-homework.md).

## Model selection (Capabilities widget)

The chat component's model picker is active **per agent**: each agent declares the
generic `simple_model_pick` provider in config (`surfaces.as_consumer.agents.<agent>`),
naming its own answer role (`lg-solution.answer` / `lg-react.answer`) and model
list. `execute_core` resolves the pick for the **active** agent and binds it onto
`bundle_call_context.role_models` around that agent's graph run — so a pick for
one agent never cross-applies to the other. No pick → the router's configured
default (fail-open). See [docs/README.md](docs/README.md).

## Degradation

With no provider key each agent runs its deterministic stub; with no reachable
Postgres each degrades to empty retrieval + an in-memory checkpointer. Both stream
either way — offline turns emit a single answer delta instead of a token stream.

## Both agents are run-to-completion

Each agent runs a turn to completion and does **not** consume in-turn
followups/steers; a followup sent mid-turn is promoted to the next turn (the
queued-next contract). In-turn followup/steer is an advanced reactive-port tier
neither agent implements — the correct default for a ported LangGraph agent.

## Links

- Config: [config/bundles.template.yaml](config/bundles.template.yaml),
  [config/bundles.secrets.template.yaml](config/bundles.secrets.template.yaml)
- Interface: [interface/README.md](interface/README.md)
- Design index: [docs/README.md](docs/README.md)
- Architecture: [docs/arch/README.md](docs/arch/README.md)
- Storage map: [docs/storage/README.md](docs/storage/README.md)
- Package journal: [docs/journal/README.md](docs/journal/README.md)
- Builder-agent guide: [AGENTS.md](AGENTS.md)
- Dependencies: [requirements.txt](requirements.txt)

## The generic procedure

This bundle follows the port procedure a coding agent executes against an
arbitrary Python project. The recipe (the executable steps) lives with the port
journal under `kdcube_ai_app/journal/26/07/port-your-solution-to-kdcube/`; this
bundle is the "one app, many agents" worked instance those steps point to.
