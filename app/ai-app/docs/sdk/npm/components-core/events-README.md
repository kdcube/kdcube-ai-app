---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/npm/components-core/events-README.md
title: "Component Events"
summary: "Event claim and transport helpers in @kdcube/components-core/events: components declare the events they need while hosts choose scene, Event Bus, or other transports."
status: implementation
tags: ["sdk", "npm", "components-core", "events", "claims", "transport", "scene"]
updated_at: 2026-06-23
keywords:
  [
    "@kdcube/components-core/events",
    "event claims",
    "scene transport",
    "component events",
    "Event Bus",
  ]
---

# Component Events

`@kdcube/components-core/events` is the shared client layer for component event
claims and event delivery. Components say what they need; the host decides the
transport.

```text
component
  declares claims
        |
        v
event client
  registers with host / scene transport
        |
        v
scene or runtime Event Bus
  receives events
  routes matching events
        |
        v
component handler
```

## Why This Exists

Event subscription intent belongs to the component that knows what it needs.
The scene should not contain hidden fallback subscriptions for specific widgets.

Good:

```text
usage card claims accounting.usage
stats widget claims kdcube.stats.snapshot
task list claims task_tracker.task.changed
```

Bad:

```text
scene hardcodes usage/stats/task subscriptions because a widget might forget
```

## Transport Boundary

The event client should not care whether delivery comes from:

- scene-managed SSE/Event Bus connection;
- direct component connection;
- Data Bus result stream;
- another host-provided bridge.

Transport is under the hood. Subscription intent remains in the component.

## Source Files

- `npm/packages/components-core/src/events/claims.ts`
- `npm/packages/components-core/src/events/client.ts`
- `npm/packages/components-core/src/events/sceneTransport.ts`
- `npm/packages/components-core/src/events/types.ts`

## Related Docs

- `docs/sdk/events/event-subsystem-README.md`
- `docs/sdk/solutions/ecosystem-component/event-subscription-and-transport-README.md`
- `docs/sdk/solutions/scene/scene-event-orchestration-README.md`

