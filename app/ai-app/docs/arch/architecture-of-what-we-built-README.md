---
id: repo:kdcube-ai-app/app/ai-app/docs/arch/architecture-of-what-we-built-README.md
title: "Architecture Of What We Built"
summary: "Runtime and service architecture of the KDCube platform: ingress, proxy, auth, processor, storage, relay, queues, Data Bus, scheduled jobs, apps, and deployment."
status: current
tags: ["arch", "architecture", "runtime", "services", "ingress", "proc", "deployment"]
updated_at: 2026-06-23
keywords:
  [
    "platform architecture",
    "runtime architecture",
    "service architecture",
    "ingress",
    "processor",
    "redis",
    "data bus",
    "event bus",
    "cron",
    "scheduled jobs",
    "apps",
  ]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/arch/architecture-of-what-you-build-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/arch/architecture-short.md
  - repo:kdcube-ai-app/app/ai-app/docs/arch/architecture-long.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/bundle/bundle-interfaces-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/bundle/bundle-transports-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/comm/conversation-event-bus-and-data-bus-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/comm/data-bus-README.md
---
# Architecture Of What We Built

This is the physical/runtime architecture of KDCube itself. It explains the
platform that loads apps, serves widgets, authenticates users, routes requests,
runs agent turns, stores artifacts, and delivers events.

For the architecture an app builder composes on top of this runtime, read
[Architecture Of What You Build](architecture-of-what-you-build-README.md).

## Runtime Map

```text
browser / external client
  |
  v
web proxy / auth gate
  |
  +-- static web UI and public widget assets
  +-- REST/API ingress
  +-- SSE / Socket.IO ingress
  +-- Data Bus publish ingress
  |
  v
chat ingress / gateway
  |
  +-- auth/session/project resolution
  +-- backpressure/rate/economics admission
  +-- upload and hosted file endpoints
  +-- stream fanout attachment
  +-- enqueue chat turns and data-bus messages
  |
  v
Redis-backed runtime fabric
  |
  +-- ready queues
  +-- conversation event lanes
  +-- comm relay Pub/Sub
  +-- Data Bus streams
  +-- background job streams
  +-- cron locks and scheduler coordination
  +-- provider discovery and cache
  |
  v
processor workers
  |
  +-- load app entrypoints
  +-- run ReAct conversations
  +-- invoke tools / MCP / APIs
  +-- execute Data Bus handlers
  +-- execute background jobs
  +-- run due cron scans
  +-- host named-service provider/client calls
  +-- emit service events and accounting usage
  |
  v
storage and external services
  |
  +-- app storage / artifacts
  +-- Postgres / RDS
  +-- Redis / ElastiCache
  +-- S3 / EFS where configured
  +-- LLM/search/embedding providers
```

## What This Layer Owns

| Layer | Owns |
| --- | --- |
| Proxy/auth | Browser entry, delegated auth, masked cookies, token exchange, public/static routing. |
| Ingress/gateway | Request validation, admission, stream attachment, uploads, Data Bus publish entry. |
| Processor | App loading, ReAct turns, tools, Data Bus handlers, cron/job execution, model calls. |
| Redis fabric | Queues, event lanes, streams, Pub/Sub relay, locks, discovery, runtime coordination. |
| Storage | Artifacts, app state, user/project data, indexes, hosted files. |
| Economics | Admission, reservation, accounting, usage events, snapshots. |

## App Interface Planes

The runtime exposes several ways an app can participate:

```text
@api              synchronous REST/operation call
@mcp              MCP tool/resource/server surface
@ui_widget        iframe/static widget surface
@data_bus_handler durable inbound command stream
@cron             scheduler due scan
@on_job           background job executor
named_services()  provider/client operation registry
ReAct tools       model-callable tools in a conversation
Event policies    block production/rendering for ReAct-visible context
```

These are runtime interfaces. A single app may use one or many of them.

## Relationship To Older Docs

The existing [architecture-short.md](architecture-short.md) and
[architecture-long.md](architecture-long.md) still describe important deployed
service details, especially proxy, ECS/Fargate, Redis, gateway, processor, and
storage. Their names are historical. This document is the current map readers
should use first; the older files are deeper operational references until they
are fully reworked.

## Read Next

- To understand what app builders compose: [Architecture Of What You Build](architecture-of-what-you-build-README.md)
- To understand app interfaces: [App Interfaces](../sdk/bundle/bundle-interfaces-README.md)
- To understand transport options: [App Transports](../sdk/bundle/bundle-transports-README.md)
- To understand Data Bus vs conversation events: [Conversation Event Bus And Data Bus](../service/comm/conversation-event-bus-and-data-bus-README.md)
