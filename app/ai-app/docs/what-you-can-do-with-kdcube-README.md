---
id: repo:kdcube-ai-app/app/ai-app/docs/what-you-can-do-with-kdcube-README.md
title: "What You Can Do With KDCube"
summary: "Dense product and builder overview of KDCube: how developers quickly build powerful governed AI apps, how apps become ecosystem components, which runtime surfaces they expose, and how ReAct, named services, Scene, Pinboard, APIs, MCP, events, cron, tools, and isolated execution fit together."
tags: ["docs", "product", "overview", "sdk", "platform", "app", "ecosystem", "agent", "react", "scene", "pinboard", "named-services", "exec"]
keywords: ["what is kdcube", "what can kdcube do", "ai product platform", "app runtime", "app reload", "kdcube app", "build ai app", "wrap existing app", "coding agent build app", "local to cloud workflow", "mcp endpoint", "react agent", "announce", "steer followup", "user memory", "namespace services", "named services", "scene", "pinboard", "iso runtime", "distributed exec", "streaming widgets", "artifact provenance"]
updated_at: 2026-06-23
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/quick-start-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/how-to-integrate-with-kdcube-apps-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/README.md
  - repo:kdcube-ai-app/app/ai-app/docs/arch/architecture-of-what-we-built-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/arch/architecture-of-what-you-build-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/ecosystem-component/components-ecosystem-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/ecosystem-component/ecosystem-component-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/recipes/components/README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/bundle/build/how-to-navigate-kdcube-docs-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/bundle/build/how-to-assemble-bundle-with-sdk-building-blocks-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/bundle/build/how-to-write-bundle-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/bundle/build/how-to-configure-and-run-bundle-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/bundle/versatile-reference-bundle-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/react-object-materialization-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/react-object-policy-bridge-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/scene/generic-scene-contract-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/canvas/canvas-sdk-solution-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/flow-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/event-source/event-source-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/tools/named-services-tools-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/exec/README-iso-runtime.md
  - repo:kdcube-ai-app/app/ai-app/docs/exec/distributed-exec-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/configuration/bundle-runtime-configuration-and-secrets-README.md
---
# What You Can Do With KDCube

KDCube is a platform and SDK for quickly building powerful governed AI apps:
chat workbenches, agentic operations tools, domain-object providers, UI scenes,
MCP/API integrations, scheduled automations, and generated-code assistants that
can move from local prototype to operated product without changing shape.

The first value is builder speed. KDCube gives developers reusable app
surfaces, a governed ReAct runtime, named-service object integration, Pinboard,
Scene, memory, tools, skills, artifacts, and isolated execution as platform
building blocks. The second value is that the same building blocks already sit
inside tenancy, secrets, budgets, RBAC, accounting, event control, and
deployment descriptors.

Use KDCube when an AI system needs product structure:

- a fast path from idea to real multi-surface AI app
- reusable SDK pieces instead of one-off app scaffolding
- agent/UI/domain-object interop across chat, Scene, Pinboard, APIs, MCP, and
  jobs
- runtime configuration and secrets
- user and environment isolation
- chat plus APIs plus widgets plus MCP plus scheduled work
- a governed ReAct agent runtime with timeline, tools, event sources,
  ANNOUNCE, compaction, steer/followup, and named-service materialization
- isolated execution for untrusted/model-generated code, separate from trusted
  app logic and app secrets
- app-owned state, tools, skills, files, artifacts, citations, memory,
  named-service realms, provenance, and policy
- a local-to-cloud delivery path that engineers and coding agents can follow

For the client integration map, read
[How To Integrate With KDCube Apps](how-to-integrate-with-kdcube-apps-README.md).

## 1. KDCube In One Paragraph

KDCube hosts **apps** inside isolated `tenant/project` environments. An app is a
deployable product unit: it can contain backend logic, an agent workflow, tools,
skills, APIs, widgets, a full UI, MCP endpoints, cron jobs, storage, secrets,
Data Bus handlers, Event Bus publishers/subscribers, named-service providers,
and product-specific policy. The platform supplies the runtime envelope; the
app supplies the product behavior.

```text
tenant/project = isolated environment
app            = runnable product/application unit
surface        = how users, agents, systems, or jobs enter the app
realm          = app-owned domain space exposed through refs and contracts
```

Compatibility note: some lower-level code, config, CLI commands, and existing
SDK docs still use the legacy name `bundle`, for example `bundles.yaml`,
`bundles.secrets.yaml`, `kdcube bundle reload`, and `sdk/bundle/...` docs. In
builder-facing text, the deployable unit is an **app**.

## 2. Who KDCube Is For

KDCube is useful for:

- product teams building governed AI assistants, workbenches, or workflow apps
- platform teams standardizing how multiple AI apps are deployed, isolated,
  accounted, and operated
- engineers wrapping existing apps, scripts, UIs, APIs, webhooks, or data
  services into a managed runtime
- teams that need local development and cloud deployment to use the same app
  contract
- coding agents that need a clear target shape for building runnable AI
  products instead of loose prototypes

It is not only a chatbot template. Chat is one surface of an app.

## 3. What You Can Build

Common app shapes:

| Product shape | KDCube surfaces |
| --- | --- |
| Internal AI workbench with files, tasks, memory, and reports | Chat, ReAct tools, Scene, Pinboard, widgets, rendering tools, hosted artifacts |
| Governed agent product | ReAct runtime, tool policies, event-source rendering, named-service tools, steer/followup, compaction |
| Generated-code assistant | ISO runtime, isolated exec, artifact capture, controlled tool proxying, workspace transport |
| Internal operations tool | Authenticated APIs, admin widgets, Data Bus handlers, storage, role policy |
| Public integration endpoint | Public `@api`, webhook auth, idempotent processing |
| Telegram, email, or messaging assistant | SDK integration, public webhook/OAuth callback, user registry, delivery |
| Browser/iframe app | App widget or full UI, operation APIs, shared SDK UI panels |
| Docs or data assistant | Knowledge source, MCP endpoint, search/fetch/read tools |
| Scheduled automation | `@cron`, `@on_job`, jobs stream, task/memo solution |
| Existing app wrapper | Thin KDCube app adapter around existing backend/UI/business logic |
| Named-service provider | Namespace ownership, provider-owned refs, schemas, search/get/upsert/action, block rendering, canvas actions, file hosting |
| Ecosystem component | App, widget, provider realm, MCP surface, event publisher, Data Bus handler, cron worker, or any combination |

One app can expose several of these at once.

## 4. Flagship Runtime Capabilities

KDCube is not only an app host. Two runtime capabilities are central to why the
platform exists:

```text
app
  |
  +-- trusted product/runtime surfaces
  |     APIs, widgets, MCP, cron, Data Bus handlers, provider operations
  |
  +-- governed ReAct agent runtime
  |     timeline, tools, ANNOUNCE, event-source policies, pull/read,
  |     named-service exploration/exploitation, steer/followup, compaction
  |
  +-- isolated execution boundary
        generated code, rendering jobs, heavy helpers, Docker/Fargate exec,
        artifact capture, no implicit access to app secrets
```

**ReAct is the built-in reference agent runtime.** It is a platform-governed
agent loop, not a thin wrapper over vendor tool calling. The runtime owns the
timeline, workspace, tool validation, event-source block production,
ANNOUNCE/compaction projection, recovery paths, budgets, and live control
events. This lets an app author decide what the model sees, what it can touch,
what it can mutate, and how provider-owned objects become model-visible context.

**Isolated execution is a first-class trust boundary.** Trusted app logic,
provider operations, and secrets do not share a process boundary with
untrusted/model-generated code. Generated code and heavy tools can run in local
subprocesses, Docker ISO runtime, split supervisor/executor mode, or distributed
Fargate exec while artifacts and logs still flow back into KDCube's provenance
model.

This combination is what makes KDCube different from a plain app server, a
chatbot template, or a library-level agent framework: the app can ship UI/API
surfaces, a governed agent runtime, and a safe execution substrate as one
operated product.

## 5. Why Apps Matter

An app gives one product a stable runtime identity:

- one id in `bundles.yaml`
- one `entrypoint.py` that exposes decorated surfaces
- one app config namespace
- one app secret namespace
- one storage/cache namespace
- one place to attach tools, skills, widgets, MCP, scheduled jobs, events,
  named services, and product policy

This lets an AI product be deployed, configured, reloaded, tested, and reasoned
about as a unit.

Apps can also be hot-reloaded during development and operations. The current CLI
command is still named `kdcube bundle reload <app_id>`: it reapplies the
descriptor-authoritative app registry, evicts process-local app caches,
refreshes app code/config for subsequent requests, and broadcasts the change to
running components. Platform image changes still require the normal image
rebuild/restart path.

## 6. Runtime Surfaces

KDCube apps can expose:

- **chat/on-message**: assistant or workflow response to user messages
- **operations APIs**: authenticated backend actions for UI/admin tools
- **public APIs**: webhooks and external callbacks with app-owned auth
- **widgets**: embedded app UI, Telegram Mini App, or KDCube widget
- **main UI**: full browser app surface
- **MCP endpoints**: app-served tool/resource interface for external agents
- **Event Bus / SSE**: service events, UI refresh signals, accounting usage,
  snapshots, and component subscription claims
- **Data Bus handlers**: durable app-domain messages, mutations, patches,
  annotations, and async state changes handled by `@data_bus_handler`
- **named-service provider**: namespace ownership for refs, objects, schemas,
  files, actions, renderers, and resolvers that other KDCube surfaces can
  consume generically
- **cron**: scheduled scans or recurring jobs
- **jobs**: async work submitted to the platform job stream and handled by
  `@on_job`

The same product may use several surfaces:

```text
Telegram message
  -> public webhook
  -> app entrypoint
  -> ReAct agent/tools
  -> streamed progress
  -> final Telegram response and hosted files

KDCube widget
  -> authenticated operation APIs
  -> Data Bus message for durable state mutation
  -> same app storage and user state

Canvas pin or external ref
  -> named-service provider resolves task:/mem:/domain: refs
  -> generic chat/canvas/ReAct surfaces render and act without hardcoded
     provider-specific logic
```

## 7. Ecosystem Components And Realms

An ecosystem component is a reusable participant in KDCube's events and actions
network. It may be a standalone service, UI widget, provider app, consumer app,
MCP surface, API surface, scheduled worker, event publisher, Data Bus handler,
or any combination.

The important idea is that apps can be useful at different integration depths:

```text
Stage 1: Standalone app
  owns domain data and UI
  maybe exposes API/MCP

Stage 2: Event participant
  emits service events
  consumes Event Bus/Data Bus messages
  can refresh widgets or trigger jobs

Stage 3: Scene component
  provides iframe widget route
  handles kdcube.surface.command
  emits/accepts context drag payloads
  claims live event subscriptions when embedded

Stage 4: Named-service provider
  owns object_ref namespace
  exposes object.schema/search/get/upsert/delete
  exposes object.resolve/action for UI affordances
  exposes block.produce/render for ReAct visibility
  exposes namespace presentation config

Stage 5: Agentic realm
  ReAct can explore/search/read the realm
  ReAct can mutate through schema-governed tools
  users can pin/attach realm objects with provenance
  outputs from one realm can become evidence/material for another
```

Read the full architecture map:

- [Architecture Of What You Build](arch/architecture-of-what-you-build-README.md)
- [Components Ecosystem Architecture](sdk/solutions/ecosystem-component/components-ecosystem-README.md)
- [Ecosystem Component Contract](sdk/solutions/ecosystem-component/ecosystem-component-README.md)

## 8. Scene And Pinboard

Scene is a browser host that composes multiple app surfaces and routes
commands, events, and context between them. Pinboard/canvas is a neutral board:
it stores opaque object refs, layout, comments, display cache, and context
provenance. Object meaning stays with the provider.

```text
User / Scene
   |
   +-- Chat surface
   +-- Pinboard surface
   +-- Memory surface
   +-- Task surface
   +-- Usage / stats / domain widgets
          |
          v
   context objects carry object_ref
          |
          v
   owner provider resolves:
     object.resolve
     object.action(open|preview|download)
     namespace_presentation_config
```

The scene should not hardcode provider semantics. It may use configuration to
mount surfaces and route target commands, but provider-owned actions come from
provider resolvers. Pinboard cards are proxies over provider-owned refs unless
the card is a canvas-owned object such as text, attachment, or comment.

Read:

- [Generic Scene Contract](sdk/solutions/scene/generic-scene-contract-README.md)
- [Cross-Surface Context Drag](sdk/solutions/scene/cross-surface-context-drag-README.md)
- [Canvas SDK Solution](sdk/solutions/canvas/canvas-sdk-solution-README.md)
- [Pin Operations](sdk/solutions/canvas/pin-operations-README.md)

## 9. Flagship ReAct Runtime Model

KDCube's flagship agent runtime is ReAct: a timeline-driven runtime model for
agents that must work with tools, files, events, memory, external namespace
objects, and long-running work. It is the reference runtime used by the
`versatile@2026-03-31-13-36` app.

ReAct is not a provider-native tool-calling wrapper. The runtime owns the
protocol shape, timeline, workspace, recovery paths, budgets, and event-source
policies. The model is the decision module inside that runtime.

The ReAct runtime is a custom channeled protocol, which lets it carry rich
events and artifacts:

- visible `thinking`/progress stream
- structured `ReactDecisionOutV2` actions
- streamed code channel for exec
- final summary channel for compact continuity
- tool-call and tool-result timeline artifacts
- live `followup` and `steer` events accepted through the shared timeline event
  bus while a turn is running
- an uncached ANNOUNCE block that re-renders operational state each decision
  round
- event-source block production, timeline projection, ANNOUNCE projection, and
  compaction projection
- protocol violation feedback visible to the next decision round

`followup` lets a running turn accept additional same-turn user input and can
grant bounded extra iteration credit. `steer` is a control event: it is recorded
on the current turn, interrupts active generation or cancellable tool phases
when possible, and gives ReAct a short finalize/reorient window.

ANNOUNCE is not decoration and not a cached transcript. It puts volatile
between-turn or between-round state directly in the model's attention without
rewriting old timeline blocks. Provider policies decide which blocks are
rendered into timeline, ANNOUNCE, and eventually compaction material.

Read the ReAct model in this order:

1. [ReAct Runtime Flow](sdk/agents/react/flow-README.md)
2. [ReAct State Machine](sdk/agents/react/react-state-machine-README.md)
3. [ReAct Context Layout](sdk/agents/react/context-layout.md)
4. [ReAct System Instruction](sdk/agents/react/system-instruction-README.md)
5. [ReAct Tools](sdk/agents/react/react-tools-README.md)
6. [ReAct Turn Workspace](sdk/agents/react/workspace/workspace-lifecycle-and-distribution-README.md)
7. [ReAct Event Sources](sdk/agents/react/event-source/event-source-README.md)
8. [Why Not Simply Tool Calling](sdk/agents/react/why/why-not-simply-tool-calling-README.md)

## 10. Tools, Skills, And Named Services

Tools are SDK/app capabilities, not just LLM function calls:

- `web_tools` search/fetch with source-pool provenance
- `rendering_tools` for PDF/DOCX/PPTX/PNG/HTML outputs
- `exec_tools` for isolated generated-code execution
- `ctx_tools` and `io_tools` for context, attachments, hosted files, and
  runtime reads
- `react.*` tools for workspace/artifact recovery, reading, patching, planning,
  and writing
- MCP tools exposed by configured MCP servers or app-served MCP endpoints
- named-service tools that connect an agent to configured namespace providers
  such as task, memory, canvas, or domain-specific systems
- app-local Python tools wired per agent through
  `surfaces.as_consumer.agents.<agent>.tools`

Skills are first-class. Platform/shared skills and custom app skills provide
workflow instructions and domain guidance that the agent can load before using
tools. Apps wire skills per agent through
`surfaces.as_consumer.agents.<agent>.skills`.

Named services are the bridge between app-owned domain systems and common
runtime surfaces. A provider is the owner of a namespace such as `task:`,
`mem:`, `cnv:`, or a domain-specific prefix. It defines:

- what refs mean
- which object families exist
- which schemas and mutations are valid
- how files are materialized
- how blocks render to ReAct timeline/ANNOUNCE/compaction
- how URIs resolve
- which UI/canvas actions are meaningful
- how namespace presentation is configured

A consumer connects chat, Pinboard, ReAct, widgets, or MCP to that namespace by
configuration and provider discovery, not by embedding provider-specific logic
into shared components.

See:

- [Namespace Services](sdk/namespace-services/README.md)
- [Namespace Service Integration](sdk/namespace-services/integration-README.md)
- [Object Ref Presentation And Actions](sdk/namespace-services/object-ref-presentation-and-actions-README.md)
- [ReAct Object Materialization](sdk/namespace-services/react-object-materialization-README.md)
- [Named Services Tools](sdk/tools/named-services-tools-README.md)
- [Custom Skills](sdk/skills/custom-skills-README.md)

## 11. Execution Runtime

KDCube includes an execution subsystem for generated code, heavy tools, and
tool runtimes that should not run inside the main server process.

Runtime modes include:

- in-process execution for safe lightweight tools
- isolated local subprocess execution for tools that need crash containment
- Docker ISO runtime with a trusted supervisor and restricted executor
- split Docker mode, where the supervisor and executor run in sibling
  containers with different mounts and privileges
- distributed/Fargate exec, where workspaces and app snapshots are transported
  to a remote ECS task

The ISO runtime is not tied to ReAct. It is reusable platform execution
infrastructure: an app can use it directly, expose it as a tool to another
agent, or serve a tool surface backed by it. It also acts as an execution
boundary:

- generated Python can run without network access or secret material
- approved tools can still be proxied through the supervisor
- artifacts, logs, executed programs, and tool outputs are merged back into the
  same KDCube artifact/timeline model
- app code roots, app readonly data, descriptor payloads, and execution
  workspaces are kept as separate surfaces

This lets apps use generated-code execution, rendering tools, web/search tools,
and custom isolated helpers while preserving an auditable result contract.

## 12. Streaming, Artifacts, And Provenance

KDCube is designed for observable long-running work.

The runtime can stream:

- model progress
- tool progress
- code snippets and execution contracts
- search queries, search results, and fetch results
- generated canvas artifacts
- final answers
- file metadata and hosted downloadable outputs
- app service events and domain refresh signals

Artifacts keep provenance:

- logical paths such as `fi:`, `tc:`, `ar:`, `so:`, and repository refs such as
  `repo:kdcube-ai-app/app/ai-app/docs/...`
- owner refs such as `task:issue:...`, `mem:record:...`, `cnv:<board>`
- tool call/result records
- visibility (`internal` vs user-visible/external)
- source-pool citation tokens and replacement
- hosted-file metadata
- original object stats for materialized provider objects where available

## 13. Memory And Continuity

KDCube has several memory layers with different owners and lifetimes:

| Layer | Purpose |
| --- | --- |
| timeline | current and recent turn evidence, tool calls, artifacts, messages |
| working summaries | compact continuity after pruning/compaction |
| internal conversation notes | agent-authored anchors inside conversation memory |
| durable user memory | user-visible, user-owned memory records with widget management, search, snapshots, and reconciliation |

Durable user memory is a standalone subsystem. ReAct can use it by:

- reading a top-N hotset in ANNOUNCE when enabled
- searching/reading memory when memory tools are enabled
- proposing or writing memory only when app policy allows it

User memory does not replace conversation memory. It extends the agent with
curated, cross-conversation user facts/preferences/state.

## 14. How Configuration Is Organized

Use this split:

| Scope | Examples |
| --- | --- |
| `assembly.yaml` | tenant/project, auth, ports, platform ref, storage, infra, ReAct runtime limits, tool trait policy |
| `secrets.yaml` | platform-level service secrets |
| `gateway.yaml` | gateway capacity, throttling, process limits |
| `bundles.yaml` | app registry, source refs, app props, non-secret config |
| `bundles.secrets.yaml` | app-specific secrets |
| user state | per-user credentials, preferences, runtime choices, memory records |

Do not put secrets in non-secret props. Do not put per-user runtime state into
deployment descriptors.

## 15. Turning Code Into An App

When wrapping existing code, keep the boundary clean:

```text
existing product code
  -> reusable service/helper/module
  -> thin KDCube app adapter
  -> decorated surfaces in entrypoint.py
  -> descriptors for config/secrets/source wiring
  -> local runtime test
```

Practical rules:

- keep business logic reusable and testable outside the app class
- keep KDCube decorators and runtime calls close to `entrypoint.py`
- expose APIs/widgets/MCP/cron/jobs through platform decorators
- expose durable domain mutations through Data Bus handlers when clients submit
  app-owned state changes
- expose named services when the app owns a domain ontology that other KDCube
  surfaces should resolve, render, search, or mutate generically
- wire agent tools in `surfaces.as_consumer.agents.<agent>.tools`
- wire agent skills in `surfaces.as_consumer.agents.<agent>.skills`
- define deployment config in `config/bundles.template.yaml`
- define deployment secrets in `config/bundles.secrets.template.yaml`
- document public routes, widgets, MCP, jobs, Data Bus subjects,
  named-service refs/schemas, and config in `interface/README.md`
- test with the shared app docs/test path before release

Start with the Tier 1 app docs:

1. [How To Navigate KDCube App Docs](sdk/bundle/build/how-to-navigate-kdcube-docs-README.md)
2. [How To Test An App](sdk/bundle/build/how-to-test-bundle-README.md)
3. [How To Assemble An App With SDK Building Blocks](sdk/bundle/build/how-to-assemble-bundle-with-sdk-building-blocks-README.md)
4. [How To Write An App](sdk/bundle/build/how-to-write-bundle-README.md)
5. [App Runtime Settings, Configuration, And Secrets](configuration/bundle-runtime-configuration-and-secrets-README.md)
6. [How To Configure And Run An App](sdk/bundle/build/how-to-configure-and-run-bundle-README.md)

## 16. Coding-Agent Instruction Seed

Use this when asking Claude Code, Codex, or another coding agent to build an
app:

```text
You are building a KDCube app, not a standalone script.

Read first:
- docs/what-you-can-do-with-kdcube-README.md
- docs/quick-start-README.md
- docs/arch/architecture-of-what-you-build-README.md
- docs/sdk/solutions/ecosystem-component/components-ecosystem-README.md
- docs/sdk/bundle/build/how-to-navigate-kdcube-docs-README.md
- docs/sdk/bundle/build/how-to-test-bundle-README.md
- docs/sdk/bundle/build/how-to-assemble-bundle-with-sdk-building-blocks-README.md
- docs/sdk/bundle/build/how-to-write-bundle-README.md
- docs/sdk/bundle/build/how-to-configure-and-run-bundle-README.md

Then inspect the versatile reference app for the nearest pattern.

Build the app as a thin KDCube adapter around product logic:
- entrypoint.py exposes surfaces with decorators
- agents/main.py contains the primary ReAct workflow when the app uses ReAct
- config/bundles.template.yaml wires agent tools under surfaces.as_consumer.agents.<agent>.tools
- config/bundles.template.yaml wires agent skills under surfaces.as_consumer.agents.<agent>.skills
- config templates define app props/secrets
- interface docs define routes/widgets/MCP/jobs/Data Bus subjects/named services/config
- tests verify imports, descriptors, and runtime behavior

Run locally with kdcube init/start and the current compatibility commands
`kdcube bundle reload` / `kdcube bundle config apply` using the active
descriptor set.
Do not invent runtime paths or config scopes; use the docs and reference app.
```

## 17. Implementation Limits And Honest Boundaries

KDCube gives a runtime contract, not magic:

- descriptor sets must still be correct for the target environment
- public callbacks need reachable HTTPS origins
- local platform-code changes require image rebuilds
- app reload updates app code/config, not platform code baked into images
- app secrets must be supplied through secret channels
- widgets must use the KDCube frame/runtime origin for API calls
- agent quality depends on visible docs, loaded skills, available tools, and
  configured model/runtime budgets
- durable memory writes require explicit policy and result verification
- MCP/docs knowledge sources must point at the intended repo/ref/root when a
  deployment exposes such a surface

## 18. Short Practical Framing

If you need one compact explanation:

```text
KDCube is a runtime for AI product apps.
One tenant/project is an isolated environment.
One app is one runnable product unit.
An app can expose chat, APIs, widgets, MCP, cron, jobs, tools, skills, and UI.
An app can also own durable Data Bus handlers and act as a named-service
provider: the owner of refs, schemas, objects, files, renderers, and actions
for a domain namespace.
Descriptors wire the environment; entrypoint decorators expose the app.
The current compatibility CLI command `kdcube bundle reload` updates app
code/config without rebuilding the platform image.
The same contract supports local development and cloud deployment.
```
