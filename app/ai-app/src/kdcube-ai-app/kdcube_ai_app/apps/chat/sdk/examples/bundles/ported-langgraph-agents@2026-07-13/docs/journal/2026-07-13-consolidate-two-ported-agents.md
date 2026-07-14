---
id: ported-langgraph-agents@2026-07-13/docs/journal/2026-07-13-consolidate-two-ported-agents
title: "2026-07-13 — Consolidate two ported agents into one multi-agent app"
status: historical
tags: ["ported-langgraph-agents", "journal", "multi-agent", "dispatch", "consolidation"]
---

# 2026-07-13 — Consolidate two ported agents into one multi-agent app

> Historical implementation record. Current code rebuilds each graph for one
> turn, uses `langchain.agents.create_agent`, and stores app-owned rows in one
> tenant/project schema with `agent_id` row/key scope. References below to a
> process-cached graph, `create_react_agent`, or per-agent schemas are obsolete;
> use the app README, architecture, and storage docs for current behavior.

## What changed

The two single-agent port bundles were merged into ONE app,
`ported-langgraph-agents@2026-07-13`, that hosts BOTH ported LangGraph agents and
dispatches them by `agent_id` through a single `execute_core`. This is the "one
app, many agents" demonstration.

- **lg-solution** — the rich research graph (dedicated answer node), vendored under
  `solution/lg_solution/`.
- **lg-react** — the prebuilt `create_react_agent` (looping agent node), vendored
  under `solution/lg_prebuilt/`.

Both `solution/` subpackages are byte-for-byte the "before" agents; only the
platform glue moved and grew.

## The dispatcher

`execute_core` became a dispatcher over a per-agent `AGENTS` registry. Each
`AgentSpec` carries `build_graph`, `stream`, `build_inputs`, `role`, and a per-agent
storage `schema`. The turn resolves `agent_id = normalize(state["agent_id"]) or
DEFAULT_AGENT_ID` (unknown → default `lg-solution`), builds that agent's graph via a
**per-agent lazy cache** (`_ensure_graph(agent_id)`), shapes its inputs, and runs it
through **its own stream adapter** — the dedicated-answer-node
`platform/stream_solution.py` for lg-solution, the looping-agent-node
`platform/stream_prebuilt.py` for lg-react. The teaching point is preserved:
different agent shapes → different stream adapters, selected by `agent_id`.

## Isolation choices

- **Identity** (`platform/identity.py`): the shared `turn_identity` gate now folds
  the active `agent_id` into `user_id` (`{tenant}:{project}:{agent}:{user}`) and
  scopes `thread_id` by it, so the two agents' per-user memories can never mix.
- **Storage** (`platform/pg_target.py`): each agent gets its OWN schema on KDCube's
  shared Postgres when hosted — `ported_langgraph_agents__lg_solution` /
  `ported_langgraph_agents__lg_react` — via `agent_schema(agent_id)`. The
  standalone (`DATABASE_URL`) and offline (MemorySaver) fallbacks are kept. Two
  mechanisms (per-agent schema + the agent_id fold) guarantee isolation.

## Config + capabilities

`config/bundles.template.yaml` declares two agents under
`surfaces.as_consumer.agents` (`lg-solution` → role `lg-solution.answer`,
`lg-react` → role `lg-react.answer`), each with its own `simple_model_pick`
picker and model list. `platform/capabilities.resolve_turn_role_models(ep, state,
agent_id)` resolves the ACTIVE agent's pick, so a pick for one agent never
cross-applies. The Telegram ingress and economics config carry over unchanged; the
webhook drives the default agent.

## Retired + preserved

- The two single-agent source bundles (the standalone lg-solution port and the
  standalone lg-react port) were removed — their solutions + stream adapters are
  folded in here.
- The standalone POCs (`poc/lg-solution`, `poc/lg-react-agent`) are untouched.

## Validation

`python -m py_compile` passes for all glue + both vendored packages. The offline
bundle test suite passes (no DB, no API key): dispatch (both agents run their own
graph + adapter, isolation holds, unknown agent falls back), identity/agent fold,
per-agent storage schema, per-agent capabilities pick, both stream adapters,
tools-both-ways, the Telegram webhook boundary, and the interface/config/OpenAPI id
agreement. An offline smoke of `execute_core` runs BOTH agents end to end and sets a
non-empty `final_answer`.
