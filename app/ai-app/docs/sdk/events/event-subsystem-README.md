---
id: ks:docs/sdk/events/event-subsystem-README.md
title: "SDK Events Subsystem"
summary: "Shared event-source declarations and discovery used by tools today and by broader SDK event flows over time."
status: draft
tags: ["sdk", "events", "event-source", "tools", "react"]
keywords:
  [
    "event_source",
    "event_source_id",
    "event_id",
    "EventSourceSubsystem",
    "tool-backed event source",
    "event policies",
  ]
see_also:
  - ks:docs/sdk/events/external-events-README.md
  - ks:docs/sdk/agents/react/event-source/event-source-README.md
  - ks:docs/sdk/agents/react/event-source/block-production-README.md
  - ks:docs/sdk/tools/tool-subsystem-README.md
  - ks:docs/sdk/tools/custom-tools-README.md
  - ks:docs/sdk/agents/react/design/timeline-events-transport-lifecycle-README.md
---
# SDK Events Subsystem

The SDK events subsystem provides shared event-source identity and discovery.
ReAct is the first consumer, but the model is wider than ReAct: the same source
identity can describe tool calls, external UI events, authored external events,
and future event-producing SDK surfaces.

## Core Model

An event source has two identities:

| Term | Meaning |
|---|---|
| `event_source_id` | Stable semantic source key, such as `web_tools.web_search`, `react.followup`, or `bundle.wizard.field_changed`. |
| `event_id` | One occurrence of that source. For tool-backed events this is the tool call id. |

A tool call is the first implemented special case of an event source:

```text
tool_id      == event_source_id
tool_call_id == event_id
```

The tool still executes through the normal tool subsystem. Event-source metadata
only tells downstream consumers how to validate, produce, project, announce, or
compact the occurrence.

## Declaration

Event sources are declared with `@event_source(...)` or returned from
`list_event_sources()` / explicit event-spec modules.

```python
from kdcube_ai_app.apps.chat.sdk.events import event_source

@event_source(
    event_source_id="{alias}.search",
    policies=[
        {
            "react_phase": "block_production",
            "event_policy_id": "react.block_production.generic_result_item",
        },
    ],
    kind="react.tool",
    reactive=False,
)
async def search(...):
    ...
```

Policy bindings are consumer-specific. Today the supported consumer is ReAct,
so bindings use `react_phase` and `event_policy_id`. The shared SDK events
subsystem does not define ReAct timeline behavior by itself.

For non-tool external events, the declaration can also define ReAct admission
defaults:

```python
from kdcube_ai_app.apps.chat.sdk.events import event_source_declaration

def list_event_sources():
    return [
        event_source_declaration(
            event_source_id="my_app.wizard.assistance.requested",
            kind="react.external",
            reactive=True,
            iteration_credit=2,
            policies=[
                {
                    "react_phase": "timeline_projection",
                    "event_policy_id": "my_app.timeline_projection.wizard_event",
                },
            ],
        )
    ]
```

`reactive` is declaration metadata/default for code that authors occurrences of
this source. Transported `external_event` occurrences must still carry their
effective `payload.external_event.routing.reactive` value; the runtime does not
silently wake ReAct from a declaration alone. `iteration_credit` is the default
live-turn credit for one occurrence that is explicitly reactive. A client
occurrence may override credit with
`payload.external_event.routing.iteration_credit`; runtime caps always apply
last.

## Discovery

`EventSourceSubsystem` discovers event declarations from:

- loaded tool modules;
- explicit event source modules;
- declarations returned by `list_event_sources()`;
- first-party built-in ReAct event modules.

The subsystem validates duplicate `event_source_id` values and lets consumers
look up declarations by source id or, when a durable block carries
`event_source_id`, by block.

## Boundary

The shared events subsystem owns:

- event-source declarations;
- identity naming;
- source discovery;
- policy binding lookup.

It does not own:

- transport delivery;
- queueing or turn ownership;
- final renderer block shapes;
- ReAct cache marker placement;
- ANNOUNCE text formatting.

Those remain responsibilities of the consuming runtime. For ReAct, see the
event-source phase documents under `docs/sdk/agents/react/event-source/`.
For conversation-scoped authored events that arrive through chat ingress, see
[External Events](external-events-README.md).
