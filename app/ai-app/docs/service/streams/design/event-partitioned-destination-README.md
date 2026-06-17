# Event-Partitioned Destinations

Status: design note, with an initial implementation for chat accounting event
filtering.

## Problem

Project-level streams intentionally fan out service events to all active
subscribers in the tenant/project/session scope. This is useful for shared
widgets such as usage cards, status panels, stats widgets, and scene-level
event brokers.

Some events are also meaningful only for one local surface. A concrete example
is `accounting.usage`:

- a chat turn uses it as a turn-local "Turn Cost" step;
- a canvas, memory, or task search uses it as a project usage update;
- all SSE subscribers can receive the project event.

When a chat widget treats every received `accounting.usage` event as a turn
step, a search performed by another surface appears in the chat Steps tab as if
the chat turn caused it.

## Current Event Routes

The platform currently has two relevant delivery shapes:

| Route | Scope | Consumer behavior |
| --- | --- | --- |
| `chat_step` | active chat turn stream | the chat widget may render the event inside the turn timeline/steps |
| `chat_service` | service/project fanout | consumers inspect the logical event type and decide whether it affects them |

`BaseEntrypoint.apply_accounting(...)` can emit both:

- `comm.event(type="accounting.usage", step="accounting", ...)` on the
  `chat_step` route;
- `comm.service_event(type="accounting.usage", step="accounting", ...)` on the
  `chat_service` route.

For a normal chat turn, both are useful:

- `chat_step` updates the visible turn cost;
- `chat_service` refreshes usage observers.

For standalone service operations, such as semantic search in canvas, memory,
or task systems, only the service/project event belongs on the stream.

## Implemented Rule

`run_accounting(..., emit_turn_event=True)` controls whether the turn-local
`chat_step` event is emitted.

Current behavior:

- chat turns keep the default `emit_turn_event=True`;
- standalone `EconomicsGuard` settlement calls
  `run_accounting(..., emit_turn_event=False)`;
- standalone search still emits `chat_service` `accounting.usage`, so usage
  widgets and scene-level observers can update.

The chat reducer also applies a defensive client-side filter:

- `accounting.usage` is accepted as a turn step only when it targets an
  existing local chat turn in the current conversation;
- historical replay applies the same conversation/turn check before using
  stored `accounting.usage` rows to populate turn cost.

This prevents older or mixed deployments from creating phantom accounting steps
for operation scopes such as `canvas_pins_search_<id>` or `memory_search_<id>`.

## Destination Ownership Model

The stream transport can remain broad. Ownership is expressed in the event
envelope and enforced by consumers.

Minimum fields currently available:

- `conversation.conversation_id`
- `conversation.turn_id`
- `event.step`
- logical event type, for example `accounting.usage`
- route, for example `chat_step` or `chat_service`

These fields are enough for the current fix because standalone search scopes use
operation ids as `conversation_id` and `turn_id`, while a chat widget knows its
local turns.

The more durable destination contract should add explicit owner fields:

| Field | Meaning |
| --- | --- |
| `origin_agent_id` | runtime/agent instance that produced the event |
| `origin_surface_ref` | UI or service surface that initiated the event |
| `target_surface_ref` | UI or service surface expected to render or act on the event |
| `target_role` | coarse audience such as `turn_timeline`, `usage_observer`, `scene_broker`, or `debug_observer` |

With those fields, consumers can filter by destination even when background
agents or multi-agent workers share the same conversation id.

## Consumer Policy

A consumer should decide whether an event is actionable for that surface before
mutating local UI state.

Examples:

- chat timeline consumes `accounting.usage` only from the turn-local channel and
  only for a known local turn;
- usage card consumes project `accounting.usage` regardless of the active chat
  turn because it is a usage observer;
- scene can relay project service events to registered surfaces based on
  `target_surface_ref` or explicit subscriptions;
- debug/telemetry sinks can record all events without rendering them as UI
  steps.

## Producer Policy

Producers should choose the narrowest meaningful route:

- turn-local events go to the turn route;
- service/project notifications go to the service/project route;
- events intended for a specific surface should include a destination field once
  `target_surface_ref` is part of the envelope.

Accounting example:

```text
Chat turn settlement
  -> chat_step accounting.usage
  -> chat_service accounting.usage

Canvas pin search settlement
  -> chat_service accounting.usage
  -> no chat_step accounting.usage
```

## Current Implementation Points

- `BaseEntrypoint.apply_accounting(..., emit_turn_event=True)`
- `BaseEntrypoint.run_accounting(..., emit_turn_event=True)`
- `EconomicsGuard._run_accounting()` passes `emit_turn_event=False`
- `components-core/src/chat/reducers.ts` filters accounting events before
  updating turn steps/cost
- `components-core/tests/chat-accounting-scope.test.mjs` covers live and
  historical filtering

## Follow-Up

Add explicit `origin_agent_id`, `origin_surface_ref`, `target_surface_ref`, and
`target_role` to service envelopes, then update consumers to use those fields as
the primary destination check. Conversation/turn matching remains a useful
secondary guard for chat-specific state.
