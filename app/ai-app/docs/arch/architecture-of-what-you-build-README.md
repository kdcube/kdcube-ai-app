---
id: repo:kdcube-ai-app/app/ai-app/docs/arch/architecture-of-what-you-build-README.md
title: "Architecture Of What You Build"
summary: "Soft architecture for app builders: how KDCube apps become ecosystem participants, service providers, scene components, named-service realms, ReAct context sources, and Pinboard objects."
status: current
tags: ["arch", "architecture", "ecosystem", "apps", "service-provider", "named-services", "scene", "react", "pinboard"]
updated_at: 2026-06-23
keywords:
  [
    "agentic network",
    "ecosystem component",
    "service provider",
    "named services",
    "realm",
    "API",
    "MCP",
    "Event Bus",
    "Data Bus",
    "cron",
    "scene",
    "pinboard",
    "ReAct",
    "provenance",
  ]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/arch/architecture-of-what-we-built-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/ecosystem-component/components-ecosystem-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/ecosystem-component/ecosystem-component-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/README.md
  - repo:kdcube-ai-app/app/ai-app/docs/recipes/components/README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/bundle/bundle-interfaces-README.md
---
# Architecture Of What You Build

This is the soft architecture an app builder creates on top of the KDCube
runtime. It explains how a regular app can remain standalone, expose APIs/MCP,
publish events, run cron, mount widgets, or become a powerful provider in the
agentic interaction network.

## Core Terminology

| Term | Meaning |
| --- | --- |
| Ecosystem component | A reusable domain participant in KDCube's events and actions network. It may be a standalone service, API, MCP server, UI widget, scene surface, provider app, scheduler, or agent tool provider. |
| App package | The deployable package that supplies one or more component roles. Some current APIs still expose a bundle id internally, but app is the builder/user-facing term. |
| Realm | A domain space owned by a component, such as tasks, memories, telemetry, documents, repositories, or conversations. |
| Named service provider | The standard provider contract that makes a realm usable by generic agents and UI surfaces through object refs, schema, search/get/upsert/action/resolve, and block production. |
| Scene | A browser host that composes multiple UI surfaces and routes commands/events/context between them. |
| Pinboard / canvas | A neutral board that stores opaque object refs, layout, comments, and context provenance; object meaning stays with the provider. |
| ReAct | The agent runtime that uses tools, context, named services, events, and block policies to reason and act. |
| Provenance | The preserved identity of where context came from, usually the canonical `object_ref` and provider metadata. |

## Interaction Planes

An app joins KDCube through one or more planes:

```text
regular app
  |
  +-- API / REST operations
  |     synchronous request/response calls
  |
  +-- MCP tools/resources
  |     tool and resource surface for agents or external clients
  |
  +-- Event Bus / SSE
  |     service events, UI refresh signals, accounting usage, snapshots
  |
  +-- Data Bus
  |     durable non-chat commands and result events
  |
  +-- Cron / scheduled jobs
  |     recurring due scans and background work handoff
  |
  +-- Named services
  |     provider-owned object/action/context plane for realms
  |
  +-- UI scene surfaces
        widgets, context drag/drop, target surfaces, surface commands
```

These planes are independent. A component can be useful with only API/MCP, only
cron, only a widget, or only events. The named-services plane is required when
the component wants generic ReAct, Pinboard, Chat, and Scene interop around
provider-owned objects.

## From Regular App To Service Provider

```text
Stage 1: Standalone app
  owns domain data and UI
  maybe exposes API/MCP
  no generic agent/object interop required

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

## Agentic Network Map

```text
                      user / scene
                           |
       +-------------------+-------------------+
       |                                       |
       v                                       v
  UI surfaces                             chat / ReAct
  scene widgets                           agent turn
       |                                       |
       | kdcube.surface.command               | named_services.*
       | context drag/drop                    | react.pull/read
       v                                       v
  Pinboard / canvas <---------------> provider realm
  stores opaque refs                   owns refs and semantics
  layout/comments                      schema/search/get/upsert
  provenance                           resolve/action/block.produce
       ^                                       |
       |                                       |
       +--------------- events ----------------+
                       Event Bus / Data Bus
                       Cron / jobs / snapshots
```

## Provider Realm Contract

To make a realm generic, the provider owns:

```text
identity:
  object_ref namespace and object families

schema:
  object.schema for create/update/delete

exploration:
  provider.about
  object.search
  object.list
  object.get

exploitation:
  object.upsert
  object.delete
  domain actions

UI actions:
  object.resolve
  object.action(open|preview|download|attach|pin-specific actions)

ReAct representation:
  event.resolve
  block.produce
  block.render when needed

presentation:
  namespace_presentation_config
  labels, icons, colors by namespace/object_kind

live behavior:
  Event Bus events
  Data Bus commands/results
  cron/job outputs where relevant
```

## Builder Read Order

1. Start with this page.
2. Read [Components Ecosystem Architecture](../sdk/solutions/ecosystem-component/components-ecosystem-README.md) for the full scene/ReAct/Pinboard map.
3. Read [Ecosystem Component Contract](../sdk/solutions/ecosystem-component/ecosystem-component-README.md) for provider and UI requirements.
4. Read [Namespace Services](../sdk/namespace-services/README.md) if the app should become a service provider.
5. Read [Component Recipes](../recipes/components/README.md) for short implementation recipes.
6. Read [App Interfaces](../sdk/bundle/bundle-interfaces-README.md) for the runtime decorators and transport details.

## Solution Interaction Map

App builders should be able to render a map of their solution's interaction
horizon from the same contracts they use to run the app. This can be a website
overlay, an internal ops page, a docs diagram, or a scene component. The map is
useful because it shows which apps, realms, surfaces, event channels, jobs, and
agent tools are connected.

The KDCube website scene architecture map is one implementation of this idea,
not a special platform-only concept.

```text
nodes:
  runtimes
  apps / app packages
  widgets/surfaces
  provider realms/namespaces
  API/MCP surfaces
  named-service operations
  Event Bus subscriptions
  Data Bus subjects
  cron/job producers
  ReAct tools/event sources
  Pinboard object resolver edges

edges:
  app -> runtime
  app -> API/MCP/Event/Data/Cron/NamedService/UI roles
  namespace -> provider app
  scene surface -> target_surface
  ReAct -> provider object.get/block.produce/upsert
  Pinboard -> provider object.resolve/action
  component -> event claim
  Data Bus subject -> handler
  cron -> job/background work
```

The map should not be a separately maintained drawing when the data already
exists in configuration, provider discovery, and component declarations. A
manual article diagram is still useful for explanation, but the inspectable
solution map should be generated from the running contracts where possible.
