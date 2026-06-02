---
id: ks:docs/sdk/events/external-events-README.md
title: "External Events"
summary: "Semantic and transport model for conversation-scoped external events, including reactive/non-reactive behavior, story targeting, Redis transport, and ReAct folding."
status: draft
tags: ["sdk", "events", "external-events", "ingress", "react", "conversation"]
keywords:
  [
    "external_event",
    "event_source_id",
    "reactive",
    "non reactive",
    "story_id",
    "payload.target",
    "conversation external event",
    "redis external event source",
    "react event source",
  ]
see_also:
  - ks:docs/sdk/events/external-events-journey-and-handling-README.md
  - ks:docs/arch/ingress/events-inception-README.md
  - ks:docs/sdk/events/event-subsystem-README.md
  - ks:docs/sdk/agents/react/event-source/event-source-README.md
  - ks:docs/sdk/agents/react/shared-timeline-event-bus-steer-followup-README.md
  - ks:docs/sdk/agents/react/runtime-configuration-README.md
---

# External Events

External events are conversation-scoped facts or intents that arrive from a UI,
transport, webhook, or system component and may be folded into a ReAct
conversation. They are not tools, but they use the same event-source identity
model:

```text
event_source_id = stable semantic source
event_id        = one occurrence
```

The ingress-level mechanics are documented in
[Ingress Event Inception](../../arch/ingress/events-inception-README.md). This
document explains the SDK semantics and how they connect to ReAct event sources.
The end-to-end transport and handling journey is documented in
[External Events Journey And Handling](external-events-journey-and-handling-README.md).

## Wire Shape

Clients send authored external events through the normal chat ingress request:

```json
{
  "message": {
    "message": "Review the draft and suggest the next step.",
    "conversation_id": "conv_...",
    "target_turn_id": "turn_...",
    "payload": {
      "target": {
        "agent_id": "invoice_wizard",
        "story_kind": "invoice_review",
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
          "snapshot_ref": "bundle:snapshots/inv_123/invoice-draft.yaml"
        }
      }
    }
  }
}
```

Field roles:

| Field | Meaning |
|---|---|
| `payload.external_event.event_source_id` | Semantic event source, used for event-source discovery and policy lookup. |
| `payload.external_event.routing.reactive` | Required effective occurrence flag when this event may wake or continue ReAct. Absence/false means no wake. |
| `payload.external_event.routing.iteration_credit` | Optional occurrence override for live iteration credit. Runtime caps still apply. |
| `payload.external_event.story_id` | Optional product/story correlation carried with the event. |
| `payload.external_event.data` | Opaque event payload owned by the bundle/application. |
| `payload.target` | Bundle-level routing metadata, such as agent id, surface, or story. |
| `target_turn_id` / `active_turn_id` | Platform turn routing fields. Do not hide these inside `payload.target`. |

## Event Source Defaults

The server-side event source declaration can describe authoring defaults for a
source:

```python
from kdcube_ai_app.apps.chat.sdk.events import event_source_declaration

def list_event_sources():
    return [
        event_source_declaration(
            event_source_id="invoice_intake.wizard.assistance.requested",
            kind="react.external",
            reactive=True,
            iteration_credit=2,
            policies=[],
            description="Wizard assistance request is authored as a reactive event by default.",
        )
    ]
```

For transported external events, reactivity is an occurrence fact. The accepted
event must carry the effective value in `payload.external_event.routing.reactive`.
This avoids silently waking ReAct for an event just because a declaration exists.

Live credit is resolved only after the occurrence is explicitly reactive:

1. `payload.external_event.routing.iteration_credit` when the occurrence sets
   it.
2. `event_source_declaration(..., iteration_credit=...)` when the source defines
   a default.
3. Runtime default `reactive_event_iteration_credit_per_event`.

The runtime cap still clamps granted credit.

Ingress is earlier than ReAct and does not load bundle declarations just to
classify an idle event. If an idle external event must start ReAct, the producer
must send `payload.external_event.routing.reactive=true`.

## Semantic Axes

External events are arranged along four independent axes.

| Axis | Values | Effect |
|---|---|---|
| Source | `event_source_id` | Selects semantic source and representation policies. |
| Occurrence | `event_id` | Identifies one accepted event. Ingress/Redis assigns this for transport-level events. |
| Reactivity | `routing.reactive` | Decides whether the event may start or extend ReAct. Absence/false means no wake. |
| Story correlation | `story_id`, `story_kind`, `payload.target` | Lets a bundle or agent tie the event to a product flow; it does not replace conversation or turn routing. |

`story_id` is intentionally semantic metadata. It helps policies, tools, and
bundle code interpret the event, but the platform still orders events by
conversation and routes active-turn delivery by turn ownership.

## Transport Path

```text
Client/UI
  sends /sse/chat or Socket.IO chat_message
        |
        v
Ingress
  validates session, bundle visibility, conversation ownership
  classifies message/followup/steer/external_event
  builds ExternalEventPayload.event
        |
        +-- current rollout: normal idle messages still enter ready queue directly
        |
        +-- external_event/followup/steer --> append Redis event lane
        |
        +-- target rollout: every accepted event is appended to lane;
            ready queue is only an id-card wake-up
        |
        v
Processor / ReAct owner
  live owner drains Redis source when active
  otherwise proc may promote eligible reactive pending task_payload as fallback
        |
        v
ReAct ContextBrowser
  converts external event into blocks
  stamps event_source_id/event_id when event-source pipeline is enabled
  contributes blocks to the active turn timeline
```

## Persistence Boundary

The shared external-event source is Redis-backed retained operational state,
scoped by an event lane:

```text
tenant + project + user_id + conversation_id + agent_id
```

The Redis keys include `user_id` and `agent_id` when the payload carries event
metadata. Payloads produced before this protocol widening fall back to the
legacy tenant/project/conversation key so retained operational events are not
lost during rollout.

```text
kdcube:chat:conversation:external-events:{tenant}:{project}:{conversation_id}:user:{user_id}:agent:{agent_id}
kdcube:chat:conversation:external-events:seq:{tenant}:{project}:{conversation_id}:user:{user_id}:agent:{agent_id}
kdcube:chat:conversation:external-events:{tenant}:{project}:{conversation_id}:user:{user_id}:agent:{agent_id}:event:{event_id}
```

`agent_id` defaults to `default.react.agent` when the producer does not target a
named agent. The implementation journey is tracked in
[External Events Journey And Handling](external-events-journey-and-handling-README.md).

Redis provides ordering, replay while retained, and crash recovery for live
owner handoff. It is not permanent conversation or artifact storage.

When ReAct folds an event, the resulting blocks and external-event cursor become
part of the normal persisted ReAct timeline. If an idle non-reactive event must
be permanent even when no ReAct turn later folds it, the bundle/platform must
also materialize it into durable conversation storage or a bundle artifact. That
durable event-history slice is separate from the current Redis transport.

## Reactive And Non-Reactive Events

Reactive events can wake or extend ReAct. Reactivity must be visible on the
occurrence:

```json
{
  "routing": {
    "reactive": true,
    "iteration_credit": 2
  }
}
```

The runtime grants bounded credit only when the active owner consumes the event
live. The effective ceiling is:

```text
effective_max_iterations = base_max_iterations + reactive_iteration_credit
```

Non-reactive events are still ordered and may be folded if an active owner
drains them, but they do not request another model decision by themselves.

`steer` remains a built-in control event. A future product can also define an
authored event whose semantics mean "stop", "pause", or "reorient"; that should
be represented by its own `event_source_id` and policy rather than by a generic
interrupt flag.

## Event Source Integration

External events connect to the SDK event subsystem by source id:

```python
from kdcube_ai_app.apps.chat.sdk.events import event_source_declaration

def list_event_sources():
    return [
        event_source_declaration(
            event_source_id="invoice_intake.wizard.assistance.requested",
            kind="react.external",
            reactive=True,
            iteration_credit=2,
            policies=[
                {
                    "react_phase": "timeline_projection",
                    "event_policy_id": "invoice_intake.timeline_projection.wizard_event",
                },
            ],
            description="Wizard user requested assistance for the active invoice story.",
        )
    ]
```

The transport does not apply these policies. It only carries the event and its
source id. ReAct applies policies later when it produces or projects blocks for
the relevant phase.

## Current Gaps

| Gap | Current behavior | Needed when required |
|---|---|---|
| Durable idle event history | Idle non-reactive events are retained only in Redis unless later folded. | Persist event facts into conversation storage or bundle-owned artifacts. |
| Custom event block builders | Built-in folding exists; richer custom source builders are still emerging. | Event-source policies for external-event block production/projection. |
| Story-specific event policies | `story_id` is carried as metadata. | Source/story policy resolution when a product flow needs different projection. |
