<p align="center">
  <img src="assets/logo.png" alt="KDCube" width="240">
</p>

# KDCube

**A platform and SDK for building, integrating, and operating multi-user AI apps.**

With KDCube you build AI apps for yourself — and just as naturally for your
team, your company, and your customers. Multi-user is the default posture;
personal use is the easy case.

An app is one deployable unit: agents, APIs, cron jobs, MCP surfaces, widgets,
and its own config and secrets. It plugs into a running platform and upgrades
almost in real time: `kdcube bundle reload <app_id>` swaps app code and config,
no image rebuild. The platform supplies the envelope every app needs in
production: isolated `tenant/project` environments, auth and roles, per-user
budgets and accounting, secret channels, streaming transports, and a
descriptor-driven delivery path that is the same locally and in the cloud.

<p align="center">
  <img src="assets/topology.svg" alt="KDCube topology: users and external agents reach your apps; apps serve and consume surfaces; the auth authority is external OIDC or a bundle; Connection Hub brokers claims; kdcube-services federates app realms over MCP" width="820">
</p>

Website: [kdcube.tech](https://kdcube.tech) · Interactive architecture:
[kdcube.tech/architecture.html](https://kdcube.tech/architecture.html)

## Quick start

```bash
pip install kdcube-cli
```

Descriptor seeds, first start, hot reload, and the app release loop:
[Quick Start](app/ai-app/docs/quick-start-README.md)

## The ReAct runtime

KDCube ships its own agent runtime. The agent perceives its input as a
**timeline of events** — ordered, authored blocks: user messages, followups
and steers, tool calls and results, artifacts, events from external systems
and other agents — folding in live under runtime policy. What the model sees,
touches, and keeps is a runtime decision, per app.

- **Live control** — `followup` feeds additional user input into a running
  turn; `steer` interrupts generation and gives the agent a reorient window.
- **Endless conversations** — compaction prunes the timeline tail, working
  summaries stand in for the pruned ranges: the window stays sharp
  indefinitely and everything the conversation ever produced stays
  retrievable through the conversational memory below. Timeline, working
  summaries, conversation notes, durable user memory — the layers of how
  ReAct remembers; context caching is the efficiency layer on top.
- **Per-turn budgets and recovery** — iteration and spend limits, protocol
  violation feedback, and recovery paths are part of the loop.
- **Citations and provenance** — web and tool results land in a sources pool;
  answers cite tokens that resolve to real sources; every artifact keeps its
  lineage.
- **Per-user memory** — durable, co-managed records: the agent proposes, a
  reconciler merges, the user edits in a widget.
- **A shared conversational realm** — every turn is indexed; `react.memsearch`
  retrieves prior turns, artifacts, and decisions across conversations with
  hybrid semantic + lexical + recency ranking. The same history is the
  searchable `conv:` realm — external agents search and reread it over MCP,
  and with external-event delivery the conversation timeline is shared
  across operators.

[Runtime flow](app/ai-app/docs/sdk/agents/react/flow-README.md) · [Timeline](app/ai-app/docs/sdk/agents/react/timeline-README.md) ·
[How ReAct remembers](app/ai-app/docs/sdk/memory/how-react-remembers-README.md) · [Conversational memory search](app/ai-app/docs/sdk/memory/conversational-memory-search-README.md) ·
[Context caching](app/ai-app/docs/sdk/agents/react/context-caching-README.md) · [Citations system](app/ai-app/docs/citations-system.md) · [User memories](app/ai-app/docs/sdk/memory/user-memories-overview-README.md)

## Isolated execution

Model-written code runs in sandboxes with no network and no secret material —
local subprocess, Docker ISO runtime, or distributed Fargate. Approved tools
are brokered through a privileged supervisor: running code is a tool call with
a tool's trust profile — declared outputs, hosted artifacts, delivery-verified
results flowing back into the timeline and provenance model.

[ISO runtime](app/ai-app/docs/exec/README-iso-runtime.md) · [Custom tools and declared files](app/ai-app/docs/sdk/tools/custom-tools-README.md)

## Connection Hub: delegated trust

Users connect their own provider accounts (Gmail, Slack, ...) with claim-scoped
consent. Consent is demand-driven — the attempt is the ask: a tool that hits
an unmet claim raises a scoped consent card in chat, and the turn keeps going.
Claims are enforced at tool boundaries: tools resolve claims, never keys;
OAuth client secrets stay in descriptors tool code cannot read. The same broker
grants external agents revocable namespace grants and mints disposable
automation tokens bound to declared resources — one click revokes token and
session.

Connect Claude — or any MCP client — to the `kdcube-services` MCP surface and
one consent unlocks every discoverable realm. Or expose your own MCP surface
around your own tools, declare claims on them, and the platform enforces them
at the boundary.

[Connection Hub](app/ai-app/docs/sdk/solutions/connections/connection-hub-solution-README.md) · [Delegated automation access](app/ai-app/docs/recipes/connections/create-delegated-automation-access-README.md)

## Named services

A domain models itself as a **realm** — `task:`, `mem:`, `mail:`, or your own —
behind one fixed grammar: `about / schema / list / search / get / action /
upsert / host_file`. One self-description serves everyone: agents read the
schema and operate through a handful of generic tools; users see the realm as
a service card. Realms federate over MCP: an external agent works the same
objects through the same grammar under delegated consent.

[Namespace services](app/ai-app/docs/sdk/namespace-services/README.md) · [Named services over MCP](app/ai-app/docs/recipes/kdcube_for_agents/named-services-mcp-README.md)

## Widgets and scenes

A widget is an app-served frontend component: the app declares it, the
platform builds and serves it — build pipeline, discovery, auth handshake —
so one app ships as many frontends as it needs. Ready-made widgets ship with
the SDK — [chat](app/ai-app/docs/recipes/components/chat-README.md),
[pin board](app/ai-app/docs/recipes/components/pinboard-README.md),
user memories, usage card, Connection Hub, the capabilities picker — and the
interaction machinery is a library too:
[`@kdcube/components-core`](app/ai-app/src/kdcube-ai-app/npm/packages/components-core) and [`@kdcube/components-react`](app/ai-app/src/kdcube-ai-app/npm/packages/components-react)
carry the scene host, config handshake, event bus, context drag, and surface
commands.

Widgets compose into chat, host pages, and scene workspaces, where a scene
assembles widgets from many apps into one page by configuration — chat,
boards, memory, domain widgets side by side. Objects drag between widgets as
context with provenance intact, surface commands route actions to the owning
widget, and a new alias mounts any deployed app's widget. Many faces come
fast: edit a widget's source and the platform rebuilds and re-serves it;
`kdcube bundle reload` upgrades the running deployment almost in real time.

[App widget integration](app/ai-app/docs/sdk/bundle/bundle-widget-integration-README.md) · [Scene contract](app/ai-app/docs/sdk/solutions/scene/generic-scene-contract-README.md) ·
[Cross-surface context drag](app/ai-app/docs/sdk/solutions/scene/cross-surface-context-drag-README.md)

## Economics

Per-user plans, budgets, and wallets. The accountable unit is the **service**:
LLM calls, embeddings, and web search ship with trackers — `@track_llm`,
`@track_embedding`, `@track_web_search` — and every accountable invocation is
attributed to the user, app, and turn that caused it, enforced before it runs,
and aggregated for operations. Accounting extends the way it ships: decorate
your function with an existing tracker (an extractor maps its result to the
usage shape) or add a tracker for a new accountable service type; scope
attribution per step with `with_accounting(component, ...)`. Cache rebuilds
are attributed too — a cold turn is marked and its premium joins the turn's
spend.

[Economics model](app/ai-app/docs/economics/economic-README.md) · [Accounting and usage tracking](app/ai-app/docs/accounting/accounting-README.md) ·
[Accountable LLM invocation](app/ai-app/docs/sdk/streaming/llm-streaming-README.md)

## Integration, both directions

An app exposes its tools and realms as MCP endpoints for external agents; its
own agents consume external MCP servers as tools — same policy, budgets, and
accounting either way. Host products pick their depth on the same surfaces:
iframe a served app UI, build native UI over the chat stream, operations APIs,
and Data Bus, or call backend-only apps from a server with no browser in the
loop. Agent code is Python inside your app: use the built-in ReAct runtime,
the Claude Code runtime, or bring your own loop — CrewAI, LangGraph, or plain
code run as app logic on the same platform surfaces.

### Where KDCube is different

| Capability | KDCube | Agent frameworks (LangGraph, CrewAI) | Agent ops platforms (LangSmith, Langfuse) |
| --- | :---: | :---: | :---: |
| Many apps on one platform, each a single deployable unit — agents, APIs, widgets, cron, MCP — plugged in and upgraded almost in real time | ✓ | ◐¹ | — |
| Multi-user identity through every layer (tenant/project/user) | ✓ | — | — |
| Per-user budgets and wallets enforced before a call runs | ✓ | — | ◐² |
| Demand-driven consent with claims enforced at tool boundaries | ✓ | — | — |
| Live turns: followup, steer, and external events fold into a shared timeline | ✓ | ◐³ | — |
| Model-written code as an isolated tool (no-network sandbox, brokered tools) | ✓ | — | — |
| Domains self-describe once — schema for agents, service cards for users | ✓ | — | — |

¹ LangGraph Platform deploys and scales agent services; the deployed unit is the graph.
² Cost and usage are traced per call and per user; spending decisions run in your code.
³ LangGraph interrupts pause a run for human input.

[How to integrate with KDCube apps](app/ai-app/docs/how-to-integrate-with-kdcube-apps-README.md) · [MCP integration](app/ai-app/docs/sdk/tools/mcp-README.md)

## Documentation

One page holds a fraction of the platform. Behind it: the Data Bus for durable
domain mutations outside chat, fairly claimed background jobs and cron,
micro-agents and subagents inside a ReAct turn, channel integrations —
Telegram bots and Mini Apps, email, LinkedIn — user automations, file storage
and hosting, monitoring and observability, per-turn cost artifacts. The map
below is the way in.

- [What you can do with KDCube](app/ai-app/docs/what-you-can-do-with-kdcube-README.md) — the product overview
- [Use cases: what problem does KDCube solve?](app/ai-app/docs/recipes/use-cases-README.md) — sixteen practitioner problems, answered with mechanisms
- [How to integrate with KDCube apps](app/ai-app/docs/how-to-integrate-with-kdcube-apps-README.md) — iframe, native UI, server, and backend-only integration modes
- [Docs index](app/ai-app/docs/README.md) — the full map
- [How to navigate the docs](app/ai-app/docs/sdk/bundle/build/how-to-navigate-kdcube-docs-README.md) — reading order for builders and coding agents
- [Architecture explorer](https://kdcube.tech/architecture.html) — interactive system map

## License

[MIT](LICENSE)
