<!--
  Suggested rewrite of README.md, focused on positioning.
  It keeps every real capability and link from the current README, but fixes the
  four weak spots in our messaging:
    - ICP: name who this is for and the trigger moment (was unnamed).
    - Ownability: lead with the one position only we hold — the self-hosted
      governed runtime / trust model.
    - Outcome clarity: say what changes for the reader, not just what we have.
    - Discoverability: use the words buyers actually search ("agent control
      plane", "self-hosted", "fleet", "governance") alongside our own terms.
  Nothing here is invented — it reframes capabilities already shipped.
-->

<p align="center">
  <img src="assets/logo.png" alt="KDCube" width="240">
</p>

<p align="center">
  <strong><span style="color:#16a34a;font-size:1.15em;">The self-hosted control plane for a fleet of AI agents and apps.</span></strong>
</p>

<p align="center">
  Tenancy, budgets, isolated execution, RBAC, and accounting as platform primitives —
  so teams that can't ship their data (or their governance) to someone else's cloud
  can run <em>more than one</em> AI application in production on infrastructure they control.
</p>

<p align="center">
  <a href="https://opensource.org/license/MIT">
    <img alt="MIT license" src="https://img.shields.io/badge/license-MIT-16a34a">
  </a>
  <a href="https://pypi.org/project/kdcube-cli/">
    <img alt="PyPI package" src="https://img.shields.io/pypi/v/kdcube-cli?label=kdcube-cli">
  </a>
  <a href="https://pypistats.org/packages/kdcube-cli">
    <img alt="PyPI downloads" src="https://img.shields.io/pypi/dm/kdcube-cli?label=downloads">
  </a>
</p>

---

## Building one AI app is easy. Running ten — governed — is hard.

The first AI demo ships in a weekend. The trouble starts at the **second and third app in production**, when someone has to answer:

- Who is allowed to run what, and which surfaces are visible to which roles?
- What did each app cost, and how do we cap it before it surprises us?
- Where does untrusted, model-generated code actually execute?
- Which events are allowed to leave our network — and which never can?
- How do we ship updates to a live app without a deployment outage?

Managed agent services, flow builders, and agent frameworks each handle part of this well. KDCube focuses on the part that is hardest to retrofit: a **governed runtime and control plane you host yourself**, where isolation, budgets, RBAC, accounting, and an outbound firewall are part of the platform rather than something you assemble per app.

## Who this is for

KDCube is built for **platform and AI-infrastructure teams in regulated or data-sensitive organizations** — financial services, healthcare, defense, government, and any org operating under a "data does not leave our boundary" rule.

You'll feel the fit if:

- you're past the first prototype and now run **several** AI apps or agents in production;
- security, legal, or compliance has ruled out shipping prompts, data, or model traffic to a vendor cloud;
- you need **self-hosted** infrastructure with the controls auditors and security reviews ask for — tenancy, role-based access, budgets, execution isolation, and provenance.

It is also relevant for product/application teams and solution builders who need to package internal AI tools with chat, UI, APIs, jobs, MCP, configuration, and owned domain state as one deployable unit.

If you want to build AI applications fast **and** keep control of runtime, tools, cost, deployment, provenance, and operations, that's the use case.

It is probably not the first tool to reach for if you only need a one-off prompt demo, a pure no-code flow builder, or a fully managed vendor-hosted agent service.

## What becomes possible

KDCube is not only a place to run a chatbot. It is a way to turn internal systems, files, workflows, and human review loops into governed AI applications that can grow past the first demo.

- **A private AI app store for your organization.** Each bundle can ship as a complete internal product with its own chat, UI, API, jobs, MCP surface, config, secrets, state, and permissions.
- **Domain objects the agent can actually understand.** Tickets, memories, files, cases, reports, incidents, customers, or any namespace you define become first-class refs with provider-owned schemas, previews, actions, and materialization paths.
- **A shared work surface, not just a chat transcript.** Chat, canvas, widgets, tasks, files, and tools can exchange context through stable refs instead of copy-pasted text.
- **Governed automation at the edge of real systems.** Agents can search, inspect, update, cite, attach, or generate objects only through configured tools, namespace contracts, and auth-aware provider operations.
- **AI products that can be operated.** Platform teams can see costs, enforce budgets, isolate execution, gate surfaces, reload configuration, and audit what each app is allowed to touch.
- **Reusable intelligence.** A bundle that owns a namespace can serve it to other bundles, agents, widgets, or external MCP clients without those consumers learning its storage model.

## Where KDCube fits

These categories overlap, and each is strong at what it is built for. KDCube's distinct combination is self-hosted and code-first, with tenancy, budgets, isolated execution, accounting, **and a reference ReAct agent runtime on board** as platform primitives rather than add-ons.

| | **KDCube** | Managed agent services<br>(AWS / Microsoft / Google) | Flow builders<br>(Dify / Flowise) | Agent frameworks<br>(LangGraph / CrewAI) |
| --- | :---: | :---: | :---: | :---: |
| Self-hosted; data stays in your boundary | ✅ | runs in their cloud | ✅ | n/a (a library) |
| Governed runtime: tenancy, RBAC, budgets | ✅ | partial, in their cloud | ❌ | ❌ |
| Isolated execution for untrusted code | ✅ | their sandbox | ❌ | ❌ |
| Reference agent runtime on board (ReAct) | ✅ | their runtime | ❌ | the loop; the runtime is yours |
| Full apps (API, UI, MCP, cron), not one loop | ✅ | varies | flows only | loop only |
| Code-first | ✅ | low-code | low-code | ✅ |
| Live control plane (enable / gate / reload/apply) | ✅ | partial | ❌ | ❌ |

The table is about fit, not ranking. KDCube's focus is governance depth plus a self-hosted runtime on infrastructure you control — including a reference ReAct agent runtime, so you are not assembling tenancy, budgets, isolation, and the agent loop yourself.

## Governance as platform primitives

These are the parts a security or platform review actually asks about, and in KDCube they are built into the runtime:

- **Isolated environments** — one `tenant/project` is one isolated environment with its own state, budgets, and configuration. Use separate environments for `dev`, `staging`, `prod`, or for deployments that must never share runtime state.
- **RBAC + surface visibility** — role-scoped control over the application *and* each individual surface (API, widget, MCP, job).
- **Budgets, rate limits, and accounting** — economic tiers, project budgets, service rate limits, price-table accounting, and billing hooks.
- **A real trust boundary** — trusted calls run through bundle tools; untrusted, model-generated code runs in isolated exec. These are not interchangeable.
- **Outbound firewall** — bundle-level control over which events are allowed to leave the runtime toward the client.
- **Live control plane** — enable, disable, gate, reload, and re-apply apps and their surfaces through runtime configuration flows, without rebuilding or redeploying the whole service for every change.

## Control over the agent runtime

Hosting is half of it. KDCube also gives the bundle author direct control over how the agent perceives and acts — the parts most stacks leave implicit:

- **How events and objects are represented to the agent.** A tool or domain object declares, through `@event_source(...)` and event policies (`react_phase = block_production / timeline_projection / announce_production / compaction_projection`), exactly how its result becomes timeline blocks and ANNOUNCE, and what the model actually sees. The agent's view of a domain object is authored, not accidental.
- **Timeline and context policies, including "cold" history.** Context length is bounded by compaction (a hard ceiling that summarizes and drops older blocks) and by age-based TTL pruning; after a cold cache, history collapses into compact semantic summary cards instead of a full replay. You can hook `on_before_compaction` / `on_after_compaction`, set the trigger (`context_max_tokens`), and tune how many recent turns stay intact and where prompt-cache breakpoints land.
- **Data retention.** Timeline retention is TTL-based (`cache_ttl_seconds`, `cache_keep_recent_turns`), and what the agent can pull into its workspace is bounded by explicit read caps (`read_visible_max_text_symbols` / `_tokens` / `_bytes`). Retention and exposure are configuration, not inherited defaults.
- **Custom ontologic namespaces.** A bundle can own a semantic namespace — `task:`, `mem:`, `cnv:`, or one you define — by implementing a **named service provider**. The provider owns refs, objects, schemas, files, block rendering, canvas actions, and URI resolution for that namespace. Consumers connect chat, canvas, and ReAct to those surfaces by configuration, without embedding bundle-specific logic in common components.
- **Per-agent tool and skill connections.** You declare exactly which tools, namespaces, operations, and skills each agent id may use. Tools live under `surfaces.as_consumer.agents.<agent>.tools`; skills live under `surfaces.as_consumer.agents.<agent>.skills`. Capability is granted per agent, not globally.
- **Per-agent model routing.** Default models per agent role, overridable by bundle config and again per invocation (`bundle_call_context.role_models`).

In short: you decide, deliberately, what the agent sees, what it can touch, what it remembers, and what it is allowed to emit.

Read more: [Bundle events & policies](app/ai-app/docs/sdk/bundle/bundle-events-README.md) · [Namespace Services](app/ai-app/docs/sdk/namespace-services/README.md) · [Agent integration](app/ai-app/docs/sdk/bundle/bundle-agent-integration-README.md) · [ReAct runtime flow](app/ai-app/docs/sdk/agents/react/flow-README.md) · [ReAct state machine](app/ai-app/docs/sdk/agents/react/react-state-machine-README.md) · [ReAct context layout](app/ai-app/docs/sdk/agents/react/context-layout.md) · [Why not simply tool calling](app/ai-app/docs/sdk/agents/react/why/why-not-simply-tool-calling-README.md)

## What you deploy: a `bundle`

A deployable AI application in KDCube is called a **bundle** — one folder of code and resources that can carry backend, frontend, APIs, widgets, MCP surfaces, scheduled jobs, configuration, storage, and runtime behavior **together**. It is not a plugin or a prompt wrapper; it is one whole application that can expose several governed surfaces at once. KDCube loads a bundle from your local filesystem or from Git by repo ref plus the bundle path.

> **Vocabulary bridge** — if you think in the buyer's terms:
> a **bundle** is one deployable AI app · a **tenant/project** is an isolated environment · **Bundle Admin** is the live control plane · the platform as a whole is your **self-hosted agent control plane / governed AI runtime**.

Typical bundle structure:

```text
my.bundle@1-0/
  entrypoint.py            # decorated surfaces: APIs, widgets, jobs, MCP, Data Bus handlers
  agents/main.py           # agent workflow when the bundle uses ReAct
  services/                # reusable bundle services/adapters
  tools/                   # optional bundle-local Python tools
  skills/                  # optional bundle-local skills
  config/                  # bundles.template.yaml + bundles.secrets.template.yaml
  interface/               # the bundle's public contract + OpenAPI
  ui/                      # scene/main app + source-folder widgets or mini apps
  docs/  resources/  tests/  requirements.txt
```

Tool and skill wiring is config-first: the reference bundle uses `surfaces.as_consumer.agents.<agent>...` configuration and `agents/main.py`.

## See it running

The landing scene runs several governed surfaces on a single page — each panel is a separate bundle widget with its own visibility and runtime boundary: a versatile chat agent, a pin-board canvas, durable user memories, a task tracker, usage/economics, and an industry-news feed. Context can be dragged between them, and any surface summoned or dismissed. It is one runtime hosting many independently governed AI surfaces.

Live demo and project site: **https://kdcube.tech/**

## What you can build

- **Internal AI workbenches** where chat, canvas, documents, tasks, memory, and domain widgets cooperate.
- **Operational assistants** that can inspect and update owned systems through explicit provider contracts.
- **Governed task/case/incident systems** where attachments, evidence, state changes, and summaries stay inside the organization boundary.
- **AI-backed APIs and MCP surfaces** that let external tools and coding agents consume the same governed capabilities.
- **Scheduled AI pipelines** for reports, monitoring, ingestion, review queues, and background enrichment.
- **Customer or employee-facing mini apps** with their own frontend plus server-side tools, jobs, config, and authorization.
- **Reusable namespace providers** that make domain objects available to chat, canvas, agents, and other bundles without leaking implementation details.

## Execution model — more than one runtime per app

One bundle is not limited to one agent or one runtime. Inside a single app you can combine blocks and give each the boundary it needs:

- **ReAct Agent** — a complete, strongly isolated agent runtime for shared and user-facing work: timeline-driven orchestration, a per-turn git-based isolated workspace, subagents, mid-turn steer and follow-up, context compaction, ANNOUNCE, and tool-driven execution. It is **not** built on provider-native tool-calling, so a model that follows the ReAct contract — including non-tool-calling models — can be the reasoning brain.
- **Claude Code** — for owner/admin coding flows and complex coding pipelines. Useful, but **not** trust-equivalent to ReAct Agent.
- **Custom Python agents** — domain-specific flows.
- **Isolated exec** — untrusted, generated code under control.
- **`@venv(...)`** — dependency-heavy Python leaf helpers.

The same bundle also holds ordinary backend logic, APIs, widgets, cron, and MCP that don't need an agent runtime at all.

Built-in SDK/runtime capabilities include Neuro Search, rendering tools (PDF / PPTX / DOCX / HTML / PNG), a managed shared Playwright browser runtime, custom tools and skills, and MCP-connected tool surfaces. Python is the native shell; Node/TypeScript backend logic sits behind a narrow bridge.

## Quick start

```bash
pipx install kdcube-cli   # or: pip install kdcube-cli
kdcube
```

Prerequisites: Python 3.9+, Git, Docker. KDCube runs on one machine with Docker Compose and carries the same environment model to EC2-style and ECS-based deployments — no cloud control plane required to start.

- [CLI installer](app/ai-app/src/kdcube-ai-app/kdcube_cli/README.md)
- [Quick Start](app/ai-app/docs/quick-start-README.md)
- [CLI deployment docs](app/ai-app/docs/service/cicd/cli-README.md)

## Build it with coding agents

KDCube documents itself for engineers **and** coding agents: a compact Tier 1 authoring pack, a reference bundle, explicit configuration/runtime ownership rules, and local run/reload/test guidance. An agent can act as creator, integrator, configurator, deployer, or QA on real bundle work.

Read this Tier 1 pack together:

1. [How To Navigate KDCube Bundle Docs](app/ai-app/docs/sdk/bundle/build/how-to-navigate-kdcube-docs-README.md)
2. [How To Test A Bundle](app/ai-app/docs/sdk/bundle/build/how-to-test-bundle-README.md)
3. [How To Write A Bundle](app/ai-app/docs/sdk/bundle/build/how-to-write-bundle-README.md)
4. [Bundle Runtime Settings, Configuration, and Secrets](app/ai-app/docs/configuration/bundle-runtime-configuration-and-secrets-README.md)
5. [How To Configure And Run A Bundle](app/ai-app/docs/sdk/bundle/build/how-to-configure-and-run-bundle-README.md)

Reference app:
- [Versatile reference bundle](app/ai-app/docs/sdk/bundle/versatile-reference-bundle-README.md) · [`versatile@2026-03-31-13-36`](app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/versatile@2026-03-31-13-36)

## Documentation

KDCube can expose documentation and domain knowledge through bundle-served MCP endpoints when a deployment configures that surface. The endpoint is deployment-specific; link the current verified docs MCP endpoint when one is available.

Start here:

- [What You Can Do With KDCube](app/ai-app/docs/what-you-can-do-with-kdcube-README.md)
- [Docs index](app/ai-app/docs/README.md)

Builder-oriented: [SDK bundle docs](app/ai-app/docs/sdk/bundle) · [Bundle docs index](app/ai-app/docs/sdk/bundle/bundle-index-README.md) · [Tools](app/ai-app/docs/sdk/tools) · [Skills](app/ai-app/docs/sdk/skills)

Platform-oriented: [Architecture](app/ai-app/docs/arch) · [Service](app/ai-app/docs/service) · [Exec / isolation](app/ai-app/docs/exec)

---

<p align="center"><sub>
Self-hosted AI agent control plane · governed AI runtime with a reference ReAct agent · for platform and AI-infrastructure teams in regulated and data-sensitive organizations.
</sub></p>
