---
id: ks:docs/arch/proc/events-orchestration-README.md
title: "Proc Events Orchestration"
summary: "Processor-side orchestration for external events: ready-queue wakeups, lane payload resolution, live-owner promotion, and boundaries with ReAct timeline folding."
status: draft
tags: ["arch", "proc", "events", "external-events", "redis", "processor", "react"]
keywords:
  [
    "proc events orchestration",
    "ExternalEventPayload",
    "ExternalEventLaneWakeup",
    "event lane",
    "ready queue wakeup",
    "processor event resolution",
    "external event promotion",
  ]
see_also:
  - ks:docs/arch/proc/processor-arch-README.md
  - ks:docs/arch/ingress/events-inception-README.md
  - ks:docs/sdk/events/external-events-README.md
  - ks:docs/sdk/events/external-events-journey-and-handling-README.md
  - ks:docs/sdk/agents/react/shared-timeline-event-bus-steer-followup-README.md
---

# Proc Events Orchestration

This note explains the processor side of the current external-event flow. It is
the queue and invocation map; event semantics and ReAct rendering policies live
in the SDK event-source docs.

## Current Shape

```text
Client
  |
  v
Ingress
  validates request
  builds ExternalEventPayload
  publishes lane-backed event to Redis event lane
  queues ExternalEventLaneWakeup for reactive lane-backed starts
  |
  v
Redis ready queue
  contains a processor wakeup, not the lane-backed request body
  |
  v
Processor
  claims queue item
  if item is ExternalEventLaneWakeup:
    read event_lane.event_id from Redis event lane
    rebuild ExternalEventPayload from event.task_payload
    attach bundle_call_context.event_lane_wakeup
  else:
    validate item directly as ExternalEventPayload
  build communicator/accounting/runtime context
  invoke bundle @on_reactive_event
  |
  v
Bundle / ReAct
  folds lane events into the timeline before model rendering
```

The important boundary is:

- the ready queue wakes proc;
- the Redis event lane owns the ordered event body;
- the bundle/ReAct runtime owns timeline folding.

## Queue Item Kinds

| Queue item | Meaning |
|---|---|
| `ExternalEventPayload` | Ordinary processor payload that already contains the event body. |
| `ExternalEventLaneWakeup` | Pointer to a lane event. It carries lane identity and queue context, but no `request`. |

`ExternalEventLaneWakeup` is intentionally small. It contains:

```text
event_lane.tenant
event_lane.project
event_lane.user_id
event_lane.conversation_id
event_lane.agent_id
event_lane.event_id
event_lane.sequence
```

Processor resolves it by calling the external-event source for that lane and
reading `event.task_payload`.

## Why The Queue Does Not Carry Request

For lane-backed starts, the accepted event already exists in the ordered lane.
If the ready queue also carried a copy of `request`, there would be two sources
of truth:

- queue order and payload copy;
- lane order and lane payload.

The current rule avoids that split:

```text
queue item = wakeup
lane event = ordered occurrence + task_payload
```

This is why BaseWorkflow/ReAct reads prompt and attachment blocks from the lane
fold, not from the wakeup object.

## Processor Resolution

When proc claims work:

1. parse the raw queue item;
2. if it is a wakeup, build the lane source from `wakeup.event_lane`;
3. read the lane event by `event_id`;
4. validate `event.task_payload` as `ExternalEventPayload`;
5. patch the event occurrence fields from the lane event;
6. add `bundle_call_context.event_lane_wakeup` for diagnostics;
7. invoke the bundle through the normal reactive-entrypoint path.

The resolved payload is still a full `ExternalEventPayload`, so communicator,
economics, runtime context, and non-ReAct workflows can use the same processor
execution machinery.

## Live Owner And Promotion

Busy-conversation `followup`, `steer`, and authored `external_event` records are
published to the same event lane.

If a live ReAct owner exists, it drains the lane and folds accepted events into
its in-memory timeline. If the live owner does not consume a promotable event,
proc can promote the retained event after the active turn completes.

Promotion queues an `ExternalEventLaneWakeup`, not a request copy. The promoted
processor task therefore goes through the same resolution path as an idle
lane-backed reactive start.

`steer` is a live control event. Proc does not promote stale steer events after
the target turn has expired.

## Non-Reactive Idle Events

An idle authored `external_event` with no ingress-visible
`routing.reactive=true` is recorded in the event lane and no proc wakeup is
queued. This keeps admission cheap and avoids waking the model for events that
do not request work.

That path is retained operational state only. Durable idle event-history
materialization is a separate pending feature.

## What Proc Does Not Own

Proc does not own:

- event-source policy declarations;
- timeline block production details;
- ReAct projection/announce/compaction behavior;
- persistent product storage for idle non-reactive events;
- final model-visible rendering.

Those live in the SDK event-source subsystem, ReAct `ContextBrowser`, and
bundle/application code.

## Relationship To Scheduler Design

The current implementation still uses the shipped processor ready queues. The
event lane now supplies per-conversation/per-agent ordering for lane-backed
events, but it is not yet the full conversation-native scheduler.

The forward-looking scheduler design is:

- [Design: Conversation Scheduler With Redis Streams](design/conversation-scheduler-streams-README.md)

That design makes conversation ownership the scheduler unit. The current
events-orchestration path is a smaller step: ordered lane events plus processor
wakeups and live-owner folding.
