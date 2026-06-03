---
id: ks:docs/arch/ingress/events-inception-README.md
title: "Ingress Event Inception"
summary: "How chat ingress classifies user messages, followups, steers, and authored external events before they enter queue, Redis external-event stream, or ReAct."
tags: ["arch", "ingress", "events", "chat", "react", "followup", "steer", "external-events"]
keywords:
  [
    "event inception",
    "external_event",
    "followup",
    "steer",
    "conversation busy",
    "reactive event",
    "iteration credit",
    "redis stream",
    "conversation timeline",
  ]
see_also:
  - ks:docs/sdk/events/external-events-README.md
  - ks:docs/sdk/agents/react/shared-timeline-event-bus-steer-followup-README.md
  - ks:docs/sdk/agents/react/runtime-configuration-README.md
  - ks:docs/sdk/bundle/bundle-client-communication-README.md
  - ks:docs/sdk/bundle/bundle-chat-stream-events-README.md
---

# Ingress Event Inception

This document describes how a client-side action becomes a platform event at
chat ingress. It is the ingress-level map; ReAct-specific folding is documented
in [Shared Timeline Event Bus for Steer and Followup](../../sdk/agents/react/shared-timeline-event-bus-steer-followup-README.md).

## Event Families

| Family | Client shape | Ingress kind | Runtime meaning |
|---|---|---|---|
| New user message | `message.message` with no busy conversation | `message` | Publish the accepted event to the lane and enqueue a reactive lane wakeup. |
| Followup | `message_kind` / `continuation_kind` / `followup=true` | `followup` | Additional same-conversation user input while a turn may be active. |
| Steer | `message_kind` / `continuation_kind` / `steer=true` | `steer` | Control/reorientation event. ReAct treats it as interrupt-like when supported. |
| Authored external event | `payload.external_event` | `external_event` | Structured product event, e.g. wizard save/request-assistance. |

`payload.target` is bundle-level routing metadata. It can identify a bundle
agent, surface, story, or local flow, but it does not own platform turn routing.
Platform turn routing stays in message-level `active_turn_id` and
`target_turn_id`.

## Authored External Event Envelope

```json
{
  "payload": {
    "target": {
      "agent_id": "invoice_wizard",
      "story_id": "invoice:inv-123"
    },
    "external_event": {
      "event_source_id": "invoice_intake.wizard.assistance.requested",
      "kind": "action",
      "story_id": "invoice:inv-123",
      "routing": {
        "reactive": true,
        "iteration_credit": 1
      },
      "data": {
        "snapshot_ref": "ext:task-tracker/inv_123/invoice-draft.yaml",
        "request": "Review this draft and suggest the next useful step."
      }
    }
  },
  "active_turn_id": "turn_...",
  "target_turn_id": "turn_..."
}
```

Rules:

- `payload.external_event.routing.reactive` is the occurrence-level reactive
  override visible to ingress.
- `payload.external_event.routing.iteration_credit` is the occurrence-level
  iteration-credit override when the event is consumed live. The runtime cap
  still applies.
- If `routing.reactive` is absent or false, the event does not wake ReAct.
  Reactive events are expensive because they run the agent, so the effective
  reactive decision must be present on the transported occurrence.
- Server-side event source declarations can still define authoring defaults,
  for example `event_source_declaration(..., reactive=True, iteration_credit=2)`,
  but producers/helpers must materialize that default into the occurrence before
  ingress receives it.
- The `external_event` object is preserved as-is in the Redis external-event
  lane payload and in the stored `ExternalEventPayload.request.payload` inside
  that lane event's `task_payload`.

## Inception Matrix

| Conversation state | Event family | Ingress action | ReAct wake/credit |
|---|---|---|---|
| Idle/new | User message | Set conversation `in_progress`, host attachments, append `kind=message` to the event lane, enqueue `ExternalEventLaneWakeup`. | Normal task budget. |
| Busy | Followup | Append to per-conversation external-event source with `kind=followup`; active owner may consume live, otherwise proc may promote fallback task. | Reactive by default; grants bounded live iteration credit. |
| Busy | Steer | Append to per-conversation external-event source with `kind=steer`; active owner may interrupt/finalize. | No iteration credit; control path. |
| Idle | Authored external event, no ingress-visible `routing.reactive=true` | Set/verify conversation row as `idle`, host attachments, append `kind=external_event` to per-conversation Redis external-event source, return `external_event_recorded`. | No wake, no credit. |
| Busy | Authored external event, no `routing.reactive=true` | Append `kind=external_event` to per-conversation Redis external-event source, return `external_event_accepted`. | No wake credit. Active owner can still fold the block if it drains the stream. |
| Idle | Authored external event, ingress-visible `routing.reactive=true` | Set conversation `in_progress`, append `kind=external_event` to the event lane, enqueue `ExternalEventLaneWakeup`. | Normal task budget. |
| Busy | Authored external event, `routing.reactive=true` | Append `kind=external_event` to per-conversation Redis external-event source, return `external_event_accepted`. | May grant bounded live iteration credit from the source default or `routing.iteration_credit`. |

## Redis External-Event Source

The external-event source is a Redis-backed ordered lane. Its identity card is:

```text
tenant + project + user_id + conversation_id + agent_id
```

Current keys include `user_id` and `agent_id` when the payload carries event
metadata:

```text
kdcube:chat:conversation:external-events:{tenant}:{project}:{conversation_id}:user:{user_id}:agent:{agent_id}
kdcube:chat:conversation:external-events:seq:{tenant}:{project}:{conversation_id}:user:{user_id}:agent:{agent_id}
kdcube:chat:conversation:external-events:{tenant}:{project}:{conversation_id}:user:{user_id}:agent:{agent_id}:event:{event_id}
```

Payloads produced before this protocol widening can still be read from the
older tenant/project/conversation key during rollout. New traffic should target
the scoped lane. The stream sequence is per lane.

Current retention:

```text
CHAT_EXTERNAL_EVENTS_STREAM_MAX_ENTRIES       default 1024
CHAT_EXTERNAL_EVENTS_STREAM_RETENTION_SECONDS default 7 days
```

This is retained operational state, not durable conversation/artifact storage.
If an event must survive Redis retention independently of ReAct folding, the
event or its payload must also be materialized into conversation storage or a
bundle/application artifact. That durable external-event history is a separate
storage slice and is not completed by the current transport implementation.

The ready queue is not the event body for lane-backed starts. It carries an
`ExternalEventLaneWakeup`, which points at the accepted lane occurrence by
`event_id` and `sequence`. Processor resolves that pointer back to the lane
event's stored `task_payload` before invoking the bundle.

## Concurrency Model

Ingress never mutates the active ReAct timeline directly.

For busy conversations:

1. Ingress reads server conversation state.
2. It records `active_turn_id_at_ingress`.
3. It reads the live owner lease, when present, and records `owner_turn_id`.
4. It appends the event to the Redis external-event source with a monotonic
   per-conversation sequence.
5. The active owner drains events from the Redis source and folds them into its
   in-memory timeline.
6. After folding, ReAct persists the resulting timeline and folded cursor.

This prevents two writers from mutating one in-memory timeline. Redis ordering
prevents accepted external events from being unordered relative to each other.
It does not yet create a single transaction across conversation state, Redis,
and durable timeline/artifact storage.

For idle non-reactive authored events, the current implementation records only
to the Redis external-event source and leaves the conversation state idle. That
is useful for low-latency event admission, but it is not sufficient as permanent
business history.

## ReAct Iteration Credit

Live reactive events can extend the active turn's effective loop ceiling:

```text
effective_max_iterations = base_max_iterations + reactive_iteration_credit
```

Credit is bounded by `reactive_event_iteration_credit_cap`. For authored
external events, the occurrence must be explicitly reactive:

```json
{
  "routing": {
    "reactive": true
  }
}
```

After the occurrence is explicitly reactive, the server-side event source
declaration can define default credit:

```python
event_source_declaration(
    event_source_id="my_app.wizard.assistance.requested",
    reactive=True,
    iteration_credit=2,
)
```

An occurrence can override that credit inside:

```json
{
  "routing": {
    "reactive": true,
    "iteration_credit": 2
  }
}
```

The runtime still clamps this through its configured cap. `steer` remains a
control path and does not mint iteration credit.

## Operator Service Events

Ingress emits operator-visible service events under the `event` namespace:

```text
event.external.recorded
event.external.accepted
```

These service events are observability signals. They are not the durable event
record itself.
