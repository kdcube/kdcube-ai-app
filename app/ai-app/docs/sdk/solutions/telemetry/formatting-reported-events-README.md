---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/telemetry/formatting-reported-events-README.md
title: "Formatting Reported Metrics"
summary: "The display vocabulary a reported metric carries -- label, format, unit -- and how a reader turns a descriptor into a caption and a formatted value with no per-metric code."
tags: ["sdk", "solutions", "telemetry", "formatting", "widgets"]
keywords: ["reported_metrics", "format", "money", "duration", "label", "unit", "percent", "generic renderer", "widget"]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/telemetry/reported-events-conventions-README.md
---
# Formatting Reported Metrics

A reported metric carries its own display intent so a reader renders it without a
local map. The data and aggregation contract -- the bag, `value`, `agg`, scope,
and the generic query -- lives in
[reported-events-conventions-README.md](reported-events-conventions-README.md);
this document owns only the three optional display hints on a descriptor
(`label`, `format`, `unit`) and how a reader consumes them.

The rule for a reader is one function: given a descriptor, produce a **caption**
(from `label`) and a **display value** (from `value` + `format` + `unit`). Adding
a metric upstream needs no reader change, because the descriptor already says how
to read it.

## The Display Hints

- `label` -- the caption. When absent, the reader humanizes the metric key:
  `articles_generated` becomes "Articles generated". A present `label` always
  wins, so an app controls its own wording.
- `format` -- the value's display kind (below). When absent or unknown, the
  reader falls back to `raw`, so an unrecognized hint degrades to a readable
  number rather than an error.
- `unit` -- an optional modifier the format reads (a currency for `money`, a time
  base for `duration`, a suffix for `raw`).

## The `format` Vocabulary

- `money` -- a currency amount. Renders `$0.47`. `unit` selects the currency
  symbol/code (default USD `$`). Small sub-cent amounts keep enough precision to
  stay non-zero.
- `duration` -- an elapsed time. `value` is seconds by default (`unit: "ms"`
  reads milliseconds). Renders compactly by magnitude: `34s`, `2m 14s`, `1h 03m`.
- `int` -- a whole count. Renders with thousands separators: `1,204`.
- `float` -- a decimal measure. Renders at a sensible fixed precision.
- `percent` -- a ratio. `value` is a fraction in `0..1` and renders `47%`
  (a `unit: "pct"` descriptor whose value is already `0..100` renders as-is).
- `bytes` -- a size. Renders humanized: `4.2 MB`.
- `raw` -- the value as text, with `unit` appended when present (`128 tokens`).
  This is the fallback for a missing or unknown `format`.

## Reader Contract

A reader is generic over the returned bag: it iterates the descriptors, formats
each, and lays them out. It does not branch on metric names. A card cell is the
caption above the display value; the reader chooses emphasis (e.g. the primary
metric larger), but never the wording or the number format -- those come from the
descriptor.

For a windowed read the query has already applied each metric's `agg` (see the
conventions doc), so the reader formats the returned `value` the same way in
every period -- latest and aggregated views share one rendering path.

Order and prominence are the reader's own presentation choice, not part of the
contract: a reader may sort by a known key set, surface one metric as the hero,
and render the rest in a grid, while still formatting each purely from its
descriptor.
