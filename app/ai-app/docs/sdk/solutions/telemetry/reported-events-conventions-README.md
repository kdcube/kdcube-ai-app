---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/telemetry/reported-events-conventions-README.md
title: "Reported Metrics Conventions"
summary: "An app reports its own operational numbers as a self-describing metric bag on a telemetry event; the stats collector preserves it verbatim and a generic query returns it back, scoped to the emitter — a new metric is one key at the emit site, with no schema, allow-list, or widget change."
tags: ["sdk", "solutions", "telemetry", "conventions"]
keywords: ["reported_metrics", "telemetry", "accounting.usage", "service_event", "agg", "data scope", "dataTenant", "self-describing metric", "stats collector"]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/service/streams/telemetry-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/comm/comm-recording-event-sinks-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/bundle/bundle-event-recording-and-sinks-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/telemetry/formatting-reported-events-README.md
---
# Reported Metrics Conventions

An app reports its own operational numbers -- spend, execution time, calls,
items produced, anything it counts -- as a self-describing bag on a telemetry
event. The stats collector preserves that bag verbatim and a generic query
returns it back, scoped to the app that emitted it, so a self-owned widget reads
its own numbers and renders them.

The design goal is **scale by addition**: a new metric is a new key in the bag at
the emit site. It flows through ingest, storage, aggregation, and the query with
no schema change, no allow-list edit, and no widget code -- the metric carries
everything the pipeline and the reader need. This is the general form of the
`reported_values` lane the MCP surface already uses (a free-form bag carried on
the event and surfaced by a query), widened to any app and any named number.

This lane rides the standard telemetry transport -- record, sink, collector
ingest -- covered in
[telemetry-README.md](../../../service/streams/telemetry-README.md). Emit is
`ChatCommunicator.service_event` (`kdcube_ai_app/apps/chat/emitters.py`); the
read side is the stats collector's `reported_metrics` query.

## The Metric Bag

The emitting app calls `service_event` and places the bag at
`data.reported_metrics`. Each entry is a self-describing descriptor keyed by
metric name:

```jsonc
{
  "type": "kdcube.news.run",      // stable event identity for this kind of run
  "reported_metrics": {
    "cost_usd":           { "value": 0.47, "agg": "sum", "label": "Model spend",       "format": "money"    },
    "execution_time_s":   { "value": 34,   "agg": "avg", "label": "Execution time",    "format": "duration" },
    "model_calls":        { "value": 47,   "agg": "sum", "label": "Model calls",        "format": "int"      },
    "tool_calls":         { "value": 12,   "agg": "sum", "label": "Tool calls",         "format": "int"      },
    "articles_generated": { "value": 3,    "agg": "sum", "label": "Articles generated", "format": "int"      }
  },
  "labels": { "channel": "news", "issue_id": "2026-07-13-news" }
}
```

A descriptor field-by-field:

- `value` (required) -- the number for this emission (one run / one event).
- `agg` (optional, default `last`) -- how a reader combines this metric across a
  window; see below.
- `label`, `format`, `unit` (optional) -- display hints the app declares so the
  widget never hard-codes its own metric. Their vocabulary and the rendering
  rules are owned by
  [formatting-reported-events-README.md](formatting-reported-events-README.md);
  this document carries only the data and aggregation contract. The hints travel
  IN the descriptor so a new metric is zero-code on the read side too.

`labels` is a separate free-form map of low-cardinality context (issue id,
channel) -- provenance for the run, not aggregated as numbers.

## Aggregation (`agg`)

The app declares how each metric combines, because only the app knows a metric's
semantics -- spend accumulates, duration averages, a running count carries its
latest value:

- `sum` -- total across the events in the window.
- `avg` -- mean across the events.
- `last` -- the most recent event's value (the default).
- `max` / `min` -- the extreme value seen.
- `count` -- number of events (the descriptor's `value` is ignored).

For the **latest** period a query returns the most recent event's descriptors as
emitted, so `agg` does not apply. For a **windowed** period (today, 7d, ...) the
reader applies each metric's own `agg` over the events in range. Because the
intent rides the metric, one query serves every app without knowing any metric.

## Identity And Scope

The communicator stamps the standard telemetry envelope onto every event, so who
reported the bag is automatic and never travels inside `reported_metrics`:

- `source_bundle` -- the app that reported (its `bundle_id`);
- `source_component`, `agent` -- finer emitter identity when set;
- `tenant` / `project` -- the scope the run belongs to;
- `type` / `name` -- the run identity the app chose (e.g. `kdcube.news.run`).

A reader selects a bag by `source_bundle` (which app) plus event `type` (which
kind of run) inside a `tenant`/`project` scope, so a widget owned by the
reporting app reads exactly its own numbers. **Cross-scope reads** follow the
same data-scope convention the usage widget uses: the reader passes `dataTenant`
/ `dataProject` and the collector serves that scope, so an app deployed in one
runtime can surface its analytics on a page served from another.

## How The Bag Flows

1. **Emit** -- the app records a `service_event` carrying `data.reported_metrics`;
   the recording selector includes the event `type` so the bag reaches the sink.
2. **Collect** -- the collector's ingest preserves the bag as-is on the event's
   open `meta`, tagged with the emitter identity and scope above. No metric name
   is enumerated on this path.
3. **Query** -- the generic `reported_metrics` query returns, for a
   `source_bundle` + `type` in a scope, either the **latest** event's descriptors
   verbatim, or each metric **aggregated** over a window by its declared `agg`.
   Descriptors keep their `label` / `format`, so the reader renders with no local
   map.

Because nothing on this path enumerates metric names, adding a metric upstream is
sufficient for it to appear downstream. This is deliberately distinct from the
collector's built-in usage and cost metrics, which are typed and rolled up for
platform-wide dashboards; the reported lane is the app-owned, self-describing
complement to them.

## Worked Example: A News Pipeline Run

Each generation run already computes its own `compute` block (cost, duration,
turn count, token usage). On completion the app reports it as a bag:

```python
await self.comm.service_event(
    type="kdcube.news.run",
    step="news.run",
    status="completed",
    data={
        "reported_metrics": {
            "cost_usd":           {"value": compute["cost_usd"],         "agg": "sum", "label": "Model spend",       "format": "money"},
            "execution_time_s":   {"value": compute["duration_seconds"], "agg": "avg", "label": "Execution time",    "format": "duration"},
            "model_calls":        {"value": compute["turn_count"],       "agg": "sum", "label": "Model calls",        "format": "int"},
            "tool_calls":         {"value": tool_calls,                  "agg": "sum", "label": "Tool calls",         "format": "int"},
            "articles_generated": {"value": 1,                           "agg": "sum", "label": "Articles generated", "format": "int"},
        },
        "labels": {"channel": channel, "issue_id": issue_id},
    },
)
```

A news-owned stats widget then reads `source_bundle = <the news app>`,
`type = "kdcube.news.run"`, with a period toggle (latest, today, 7d), and renders
each returned descriptor by its `format`. Reporting a new number later -- say
`sources_scanned` -- is one more entry here and it appears on the card with no
other change.
