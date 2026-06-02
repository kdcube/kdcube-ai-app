---
id: ks:docs/sdk/events/external-events-journey-and-handling-README.md
title: "External Events Journey And Handling"
summary: "End-to-end journey for external events from client intent through Redis ordering, live owner consumption, offline processor materialization, and timeline storage."
status: draft
tags: ["sdk", "events", "external-events", "processor", "react", "timeline", "redis"]
keywords:
  [
    "external event journey",
    "event lane",
    "agent_id",
    "id_card",
    "offline materialization",
    "live owner",
    "conversation lock",
    "event timeline",
  ]
see_also:
  - ks:docs/sdk/events/external-events-README.md
  - ks:docs/sdk/events/event-subsystem-README.md
  - ks:docs/sdk/agents/react/event-source/event-source-README.md
  - ks:docs/sdk/agents/react/shared-timeline-event-bus-steer-followup-README.md
  - ks:docs/arch/ingress/events-inception-README.md
---

# External Events Journey And Handling

This document glues together the transport side of external events, the
processor responsibility, and the semantic materialization path that turns an
event occurrence into stored timeline blocks.

The compact protocol reference is
[External Events](external-events-README.md). This document explains how the
event moves through the system.

## Key Identities

Every accepted event belongs to an event lane identified by an `id_card`:

```text
tenant + project + user_id + conversation_id + agent_id
```

`agent_id` is required conceptually from the beginning. When the client does not
target a specific agent, the platform uses:

```text
default.react.agent
```

The lane identity is separate from the event semantics:

| Identity | Meaning |
|---|---|
| `id_card` | Tenant/project/user/conversation/agent lane and timeline scope. |
| `event_source_id` | Semantic event source and policy key. |
| `event_id` | One accepted occurrence. Assigned by the transport lane. |
| `sequence` | Monotonic ordering number inside one lane. Assigned by Redis. |

## Journey

```text
Client / widget / API
  sends message, attachment, followup, steer, or authored external_event
        |
        v
Ingress
  validates session and conversation state
  resolves id_card:
    tenant, project, user_id, conversation_id, agent_id
  builds ExternalEventPayload
  publishes accepted lane events to Redis lane
        |
        v
Redis external-event source
  assigns event_id + sequence for every accepted lane event
  retains event payload while operationally needed
        |
        +-----------------------------+
        | live owner exists           |
        v                             |
Live ReAct owner                      |
  listener drains lane                |
  shared materializer builds blocks   |
  contributes blocks to active        |
  in-memory timeline                  |
        |                             |
        v                             |
Persisted timeline on turn save       |
                                      |
        +-----------------------------+
        | no live owner
        v
Processor offline materialization task
  loads bundle entrypoint
  acquires id_card timeline critical section
  calls @process_offline_events entrypoint method
  constructs agent runtime/browser without running the model
  drains non-reactive lane items only
  shared materializer builds blocks
  appends to last/synthetic timeline
  persists running timeline and turn log
```

There is one ingestion door: ingress publishes into the lane. Live handling and
offline handling are two consumers of the same ordered lane, not two different
event protocols.

The top-level ingress-to-processor envelope is `ExternalEventPayload`. It is
not necessarily chat and not necessarily a task. Its `event` field is an
`ExternalEvent` occurrence:

```text
ExternalEventPayload.event.kind
ExternalEventPayload.event.agent_id
ExternalEventPayload.event.event_source_id
ExternalEventPayload.event.event_id
ExternalEventPayload.event.sequence
ExternalEventPayload.event.reactive
```

Chat is represented as an event kind on this envelope, not as the envelope
itself.

## Current Live Listener

For a live ReAct turn, the listener is started by `ContextBrowser` when hooks
are registered and a timeline is loaded. The transport loop lives under the
ReAct events package:

```text
sdk/solutions/react/browser.py
  owns ContextBrowser, timeline, and hook registration

sdk/solutions/react/events/listener.py
  owns live Redis wait loop and owner lease refresh/release helpers
```

The live loop owns only transport mechanics:

1. refresh the owner lease
2. read events after the last timeline cursor
3. pass events to the shared materializer

It does not own event-source policy semantics.

## Offline Materialization

When there is no live owner, no process should permanently block-listen to every
idle conversation. Instead, publishing an event schedules or coalesces a
processor task for the affected `id_card`.

The processor works with the bundle entrypoint and its discovered methods. The
offline hook is therefore an entrypoint surface, not only an internal workflow
method:

```python
from kdcube_ai_app.infra.plugin.bundle_loader import process_offline_events
from kdcube_ai_app.apps.chat.sdk.events import (
    EventTimelineIdentityCard,
    ExternalEventMaterializationCtx,
    ExternalEventMaterializationResult,
)

@process_offline_events
async def process_offline_events(
    self,
    *,
    id_card: EventTimelineIdentityCard,
    materialization_ctx: ExternalEventMaterializationCtx,
) -> ExternalEventMaterializationResult:
    ...
```

This hook is not a second route for receiving events. It is the offline storage
path for already accepted **non-reactive** events when there is no live owner.
The default entrypoint implementation may delegate to BaseWorkflow/ReAct
materialization code, but proc discovers and calls the entrypoint method. A
bundle may override the entrypoint method when it owns a different event storage
model.

## Handler Inputs

`id_card` identifies the lane and storage target:

```python
EventTimelineIdentityCard(
    tenant="...",
    project="...",
    user_id="...",
    conversation_id="...",
    agent_id="default.react.agent",
    bundle_id="...",
    user_type="...",
)
```

`materialization_ctx` provides mechanisms:

```text
event_source       Redis reader for the id_card lane
ctx_client         conversation/timeline artifact access
critical_section   conversation+agent timeline mutation lock
logger             diagnostic sink
settings           runtime/materialization settings
```

Events themselves are read from the lane. They are not embedded into the
`id_card`.

## Ordering

Ordering is preserved by three rules:

1. All events for one `id_card` are written to one Redis lane and receive one
   monotonic `sequence`.
2. Live owner and offline processor use the same timeline critical section for
   timeline mutation.
3. Materialization reads gaplessly from the persisted cursor and marks events
   consumed/materialized only after timeline persistence succeeds.

If an event is appended while no turn is active, its blocks are marked as
out-of-turn:

```json
{
  "type": "event.external",
  "meta": {
    "event": {
      "agent_id": "default.react.agent",
      "event_source_id": "app.flow.saved",
      "event_id": "evt_...",
      "sequence": 42,
      "out_of_turn": true
    }
  }
}
```

Event metadata lives under `meta.event` so it does not collide with block-shape
metadata.

## Synchronization

Timeline mutation is synchronized by the platform materialization runner, not by
custom bundle code. The processor acquires the per-`id_card` timeline critical
section before invoking `@process_offline_events`; the live ReAct owner uses the
same critical section when folding stream events into the active timeline or
loading/folding pending events before render.

The critical section scope is:

```text
tenant + project + user_id + conversation_id + agent_id
```

The lock must cover:

1. reading the latest persisted timeline and cursor
2. reading the next Redis events after that cursor
3. converting accepted events into blocks
4. appending blocks to the running timeline / turn log
5. persisting the timeline
6. marking events consumed/materialized

The hook should not advance the cursor past an event it did not materialize. If
the offline handler encounters a reactive event in the lane, it stops before
that event and returns a `reactive_event_pending` handoff result to processor.
Processor then starts or promotes the stored reactive task normally.

The offline hook does not create a turn id. A reactive event that can start work
must carry its original `task_payload`; that payload includes the ingress-assigned
`routing.turn_id`. Processor uses that stored payload for the normal ready-queue
path, with claim/promotion idempotence so the same reactive event is not queued
twice.

### Concurrent Reactive Arrival

If a reactive message, followup, steer, or authored reactive external event
arrives while offline materialization is in progress:

1. ingress publishes it to the same ordered lane and receives a higher
   `sequence`
2. the Redis event stores the ingress-assigned `task_payload`, including
   `routing.turn_id`
3. ingress or the processor handoff schedules/queues reactive agent work for the
   same `id_card`
4. the reactive runtime waits on the same timeline critical section before
   loading/folding events
5. after the offline materializer persists its non-reactive prefix, the reactive
   runtime drains from the persisted cursor and sees the reactive event in
   sequence order

This keeps the timeline ordered without letting the offline handler accidentally
wake or run the agent.

### Ready Queue Is Not The Sequencer

The ready queue is only a wake-up channel. It must not define ordering for one
`id_card`.

The Redis lane sequence is authoritative. Before a reactive task starts model
work, processor must pass an `id_card` start gate:

```text
task for sequence N starts
  acquire id_card timeline critical section
  load persisted cursor
  inspect next unmaterialized lane events

  if an earlier reactive event sequence M < N exists:
    ensure/promote sequence M is queued or claimed
    release lock
    requeue/defer sequence N

  if this task is the next reactive sequence:
    materialize all preceding non-reactive events
    materialize this reactive event as the turn input/current event
    persist cursor/timeline
    continue normal ReAct startup
```

This handles the race where an offline materializer is draining events, a later
user message is already queued, and an earlier reactive event is discovered in
the lane. The later message may reach the ready queue first, but it cannot pass
the start gate while the earlier reactive sequence is still pending.

If the earlier reactive event already carries a stored `task_payload`, the
handoff uses that payload and its ingress-assigned `routing.turn_id`. If it has
not yet been queued, the gate promotes it before deferring the later task.

## Reactive And Non-Reactive

Reactive events can wake or extend an agent. Non-reactive events only need to be
stored or folded.

```text
non-reactive + live owner
  drain lane -> append blocks -> no iteration credit

non-reactive + no live owner
  schedule offline materialization -> append out-of-turn blocks -> no model run

reactive + live owner
  drain lane -> append blocks -> grant bounded credit -> continue current turn

reactive + no live owner
  publish lane event with task_payload -> start/queue agent work for id_card
  new runtime drains lane before first render/decision
```

Reactive work is expensive, so an authored event must carry the effective
reactive decision on the occurrence.

`@process_offline_events` is only for the non-reactive/no-live-owner branch. It
does not promote, start, or run reactive work. If it sees a reactive event while
draining the ordered lane, it returns a handoff result and processor uses the
event's stored `task_payload` to schedule the normal reactive path.

## Boundaries

| Component | Owns |
|---|---|
| `external_events.py` | Redis transport, sequence, stream/event storage, owner lease, claim/consume. |
| Ingress | Session validation, conversation state, event publish, ack, scheduling hint. |
| Processor | Offline materialization task execution, bundle entrypoint loading, and per-`id_card` timeline critical section ownership. |
| Bundle entrypoint | `@process_offline_events` method and agent-specific materialization delegation. |
| ReAct event materializer | Event-source policy lookup, event-to-block production, timeline contribution. |
| Timeline/browser | Loading/persisting timeline artifacts and applying ordered block contributions. |

The event timeline is not inherently ReAct. It becomes a ReAct timeline when the
bundle handles it through the ReAct materializer. The storage/ordering contract
is intentionally generic enough to be reused later.

## Implementation Status

| Capability | Status |
|---|---|
| Redis external-event source, sequence, owner lease | Implemented. |
| Live ReAct listener | Implemented; transport loop is in `sdk/solutions/react/events/listener.py`. |
| Event-source declarations and ReAct policies | Implemented for tool block production; timeline/announce/compaction phases are in progress. |
| `agent_id` in lane scope and `RuntimeCtx` | Implemented with fallback for retained payloads that do not yet carry `event`. |
| `ExternalEventPayload` protocol name | Implemented as the top-level ingress-to-processor event envelope. |
| Processor offline materialization task | Target design; pending implementation. |
| `@process_offline_events` entrypoint surface | Decorator and manifest discovery implemented; processor invocation pending. |
| Shared live/offline event materializer | Target design; extraction pending. |
