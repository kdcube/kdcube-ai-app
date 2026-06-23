---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/npm/components-core/host-event-bus-README.md
title: "Host Event Bus"
summary: "Typed outbound events from a component engine to its host: unauthorized, object-open, view-change, pin-conversation, canvas-patch, context-removed, service-notice, connection, ready, and error."
status: implementation
tags: ["sdk", "npm", "components-core", "events", "host", "chat", "scene"]
updated_at: 2026-06-23
keywords:
  [
    "host event bus",
    "engine.on",
    "HostEventMap",
    "object-open",
    "pin-conversation",
    "canvas-patch",
  ]
---

# Host Event Bus

The host event bus is the outbound control channel from an engine to its host.
The engine emits; the host reacts. The engine does not know whether the host is a
website scene, iframe adapter, React page, or another shell.

```ts
const off = engine.on('object-open', ({ ref }) => openInScene(ref))
off()
```

## Events

| Event | Payload | Host responsibility |
| --- | --- | --- |
| `unauthorized` | `{ status?, reason? }` | Show login or refresh credentials. |
| `object-open` | `{ ref }` | Resolve/open a referenced object through scene/provider routing. |
| `view-change` | `{ view }` | Resize, dock, expand, or ignore. |
| `pin-conversation` | `{ conversationId, title?, ref?, context?, contexts? }` | Convert the active chat context into canvas ingress/pin action. |
| `canvas-patch` | `{ event }` | Forward a backend canvas patch event to a board if the host has one mounted. |
| `context-removed` | `{ ids }` | Sync context-chip removal back to source surfaces if needed. |
| `service-notice` | `{ text, tone, kind? }` | Show or log a user-facing notice. |
| `connection` | `{ status, detail? }` | Observe transport state. |
| `ready` | `{}` | Observe engine readiness. |
| `error` | `{ error, fatal?, context? }` | Log or surface non-fatal/fatal engine errors. |

## Inbound Direction

Host-to-engine control is not another event bus. The host calls methods:

```ts
engine.loadConversation(id)
engine.attachContext(items)
engine.removeContext(ids)
engine.setHostView('expanded')
engine.refreshAuth()
```

Iframe or scene adapters may translate postMessage or scene commands into those
method calls, but the core engine contract remains method-based.

## Relation To Scene

The scene has its own runtime/event bus for mounted surfaces. The host event bus is
local to a component engine. A scene adapter may bridge `object-open` or
`pin-conversation` into scene surface commands or `kdcube.canvas.ingress`.
