---
id: ks:docs/sdk/events/external-events-journey-and-handling-README.md
title: "External Events Journey And Handling"
summary: "Current end-to-end journey for conversation-scoped external events: ingress admission, Redis lane ordering, ready-queue wakeups, processor resolution, and ReAct timeline folding."
status: draft
tags: ["sdk", "events", "external-events", "processor", "react", "timeline", "redis"]
keywords:
  [
    "external event journey",
    "event lane",
    "agent_id",
    "id_card",
    "ExternalEventPayload",
    "ExternalEventLaneWakeup",
    "live owner",
    "conversation event lane",
    "event timeline",
  ]
see_also:
  - ks:docs/sdk/events/external-events-README.md
  - ks:docs/sdk/events/event-subsystem-README.md
  - ks:docs/sdk/agents/react/event-source/event-source-README.md
  - ks:docs/sdk/agents/react/shared-timeline-event-bus-steer-followup-README.md
  - ks:docs/arch/ingress/events-inception-README.md
  - ks:docs/arch/proc/events-orchestration-README.md
---

# External Events Journey And Handling

This document describes the current event path from client action to processor
execution and ReAct timeline folding.

The compact semantic protocol is in
[External Events](external-events-README.md). Ingress classification is in
[Ingress Event Inception](../../arch/ingress/events-inception-README.md).
Processor responsibilities are summarized in
[Proc Events Orchestration](../../arch/proc/events-orchestration-README.md).

## Identities

Every accepted lane event belongs to one lane identity:

```text
tenant + project + user_id + conversation_id + agent_id
```

When the client does not name an agent, the platform uses:

```text
default.react.agent
```

The lane identity is separate from event semantics:

| Identity | Meaning |
|---|---|
| `id_card` | Tenant/project/user/conversation/agent lane and timeline scope. |
| `event_source_id` | Semantic event-source and policy key. |
| `event_id` | One accepted occurrence. Assigned by the event lane. |
| `sequence` | Monotonic ordering number inside one lane. Assigned by Redis. |

For tool-backed events inside ReAct, `tool_id` is equivalent to
`event_source_id` and `tool_call_id` is equivalent to `event_id`.

## Current Journey

```text
Client / widget / API
  sends user message, attachment, followup, steer, or authored external_event
        |
        v
Ingress
  validates auth/session/conversation
  resolves agent_id from payload.target.agent_id or default.react.agent
  builds ExternalEventPayload
  publishes the accepted occurrence to the Redis event lane when the event is
  lane-backed
        |
        +-- idle reactive event
        |     queue ExternalEventLaneWakeup
        |     wakeup points at the lane event; it does not carry request data
        |
        +-- busy followup / steer / external_event
        |     retain in the same lane for the live owner
        |     if not consumed live, proc can promote the retained event later
        |
        +-- idle non-reactive authored external_event
              retain in the lane and return; no model wake
        |
        v
Redis event lane
  assigns event_id + sequence
  stores the occurrence payload and stored task_payload while retained
        |
        v
Processor ready queue
  carries either an ordinary ExternalEventPayload or an ExternalEventLaneWakeup
        |
        v
Processor
  if queue item is ExternalEventLaneWakeup:
    reads the lane event by event_id
    reconstructs ExternalEventPayload from event.task_payload
    annotates bundle_call_context.event_lane_wakeup
  invokes bundle @on_reactive_event with the resolved payload
        |
        v
ReAct ContextBrowser / BaseWorkflow
  folds lane events into timeline before first model render
  live listener drains later lane events while the turn owns the lane
  BaseWorkflow skips duplicate inline prompt/attachment contribution when the
  lane reader already materialized current-turn user input
```

There is one event protocol: `ExternalEventPayload`. The ready queue may carry
a small `ExternalEventLaneWakeup`, but that wakeup is only a pointer to the
accepted lane occurrence. It is not the event body.

## Payloads

`ExternalEventPayload` is the top-level ingress-to-processor event envelope. It
is not necessarily chat and not necessarily a task:

```text
ExternalEventPayload.event.kind
ExternalEventPayload.event.agent_id
ExternalEventPayload.event.event_source_id
ExternalEventPayload.event.event_id
ExternalEventPayload.event.sequence
ExternalEventPayload.event.reactive
```

`ExternalEventLaneWakeup` contains the service/routing/user context needed by
the processor queue machinery, plus:

```text
ExternalEventLaneWakeup.event_lane.tenant
ExternalEventLaneWakeup.event_lane.project
ExternalEventLaneWakeup.event_lane.user_id
ExternalEventLaneWakeup.event_lane.conversation_id
ExternalEventLaneWakeup.event_lane.agent_id
ExternalEventLaneWakeup.event_lane.event_id
ExternalEventLaneWakeup.event_lane.sequence
```

It intentionally does **not** contain `request`. The prompt, attachments,
followup text, steer text, or authored event payload are recovered from the lane
event's stored `task_payload`.

## User Messages As Events

New lane-backed user input uses event kind:

```text
message
```

The ReAct lane-to-timeline fold converts `kind=message` into ordinary
`user.prompt` blocks. Attachments on the same lane event become
`user.attachment.*` blocks.

During rollout, retained lane records may still have `kind=regular`. The fold
normalizes those retained records exactly like `kind=message`; new producers
should use `message`.

This conversion is important because prompt blocks are the inputs later handled
by normal BaseWorkflow persistence and indexing, including
`persist_turn_prompt_entries()`.

## Other Event Kinds

The current fold maps retained lane events to timeline blocks like this:

| Lane event kind | Timeline block shape |
|---|---|
| `message` | `user.prompt` plus optional `user.attachment.*` |
| `followup` | `user.followup` plus optional external attachment blocks |
| `steer` | `user.steer` |
| `external_event` | `event.external` plus optional external attachment blocks |

When the ReAct event-source pipeline is enabled, folded blocks are stamped with
event identity:

```json
{
  "meta": {
    "event_source_id": "chat.message",
    "event_id": "m...",
    "sequence": 12
  }
}
```

Tool blocks may keep using the existing tool-call identity instead of
duplicating the same fields on every durable block.

## Live Owner Path

For a live ReAct turn, `ContextBrowser` registers external-event hooks and owns
the timeline. The Redis wait loop lives in:

```text
sdk/solutions/react/events/listener.py
```

The loop owns transport mechanics only:

1. acquire/refresh the owner lease
2. read lane events after the current cursor
3. call the supplied fold/materialization callback
4. mark consumed events only after they were applied

Event-source policy semantics stay outside the Redis listener.

## Promotion Path

If a busy-conversation event is not consumed by a live owner, proc may promote
the oldest promotable retained event after the current turn completes.

Promotion now queues an `ExternalEventLaneWakeup`, not a copy of the request
body. The processor resolves that wakeup back to the lane event before invoking
the bundle.

`steer` is not promoted after the active turn expires; it is a live control
event.

## Non-Reactive Idle Events

An authored `external_event` with no ingress-visible
`routing.reactive=true` does not wake ReAct. In the current implementation it is
recorded in the Redis event lane and the conversation remains idle.

That lane is retained operational state:

```text
CHAT_EXTERNAL_EVENTS_STREAM_MAX_ENTRIES       default 1024
CHAT_EXTERNAL_EVENTS_STREAM_RETENTION_SECONDS default 7 days
```

It is not permanent business history. If an idle non-reactive event must be a
durable product fact before a later turn folds it, the bundle/platform needs a
separate durable event-history or artifact materialization path.

## Ordering

For one `id_card`, Redis lane `sequence` is the event order. The ready queue is
a wake-up channel and must not be treated as the ordering source.

Current ordering boundaries:

- accepted lane events are ordered per `id_card`
- a live ReAct owner folds events from the lane cursor in order
- processor resolves lane wakeups by event id before bundle invocation
- full durable out-of-turn timeline materialization for idle non-reactive events
  is not yet implemented

Because the current durable ReAct timeline is still persisted by turns,
out-of-turn non-reactive events can be retained in Redis before any later turn
folds them. The planned durable event-history work should make that storage
explicit instead of pretending Redis retention is permanent conversation
history.

## Boundaries

| Component | Owns |
|---|---|
| Ingress | Auth/session validation, event classification, agent target resolution, lane publish, wakeup enqueue, service ack. |
| Redis event lane | Per-`id_card` event order, retained event payload, sequence, event lookup, owner lease, promotion claim metadata. |
| Ready queue | Processor wakeups and ordinary proc scheduling. It does not store the lane-backed event body. |
| Processor | Queue claim, wakeup resolution, communicator/accounting context, bundle invocation, promotion after unconsumed busy events. |
| ReAct ContextBrowser | Lane-to-timeline folding before first render and during live turns. |
| Event-source subsystem | Source declaration and policy lookup. It does not own transport or processor queueing. |

## Implementation Status

| Capability | Status |
|---|---|
| `ExternalEventPayload` as top-level envelope | Implemented. |
| `agent_id` in lane scope and RuntimeCtx | Implemented. |
| Redis external-event lane sequence and owner lease | Implemented. |
| Ready-queue `ExternalEventLaneWakeup` | Implemented for lane-backed reactive starts and promoted retained events. |
| Wakeup without request body | Implemented; proc resolves event body from lane `task_payload`. |
| Lane-backed ReAct turn input | Implemented; ContextBrowser folds lane events before first model render. |
| BaseWorkflow duplicate prompt/attachment guard | Implemented. |
| Workflow raw event callback | Implemented as `BaseWorkflow.on_external_event_received(...)`; default no-op. |
| Durable idle non-reactive event-history materialization | Pending. |
| Full conversation-native scheduler | Design only; see proc scheduler design docs. |
