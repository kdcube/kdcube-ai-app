---
id: ks:docs/sdk/agents/react/plan-README.md
title: "Plan"
summary: "How React v2 creates, supersedes, rereads, and closes plans across turns."
tags: ["sdk", "agents", "react", "plan"]
keywords: ["plan blocks", "announce", "plan lifecycle", "active plan", "plan acknowledgements"]
see_also:
  - ks:docs/sdk/agents/react/react-announce-README.md
  - ks:docs/sdk/agents/react/react-round-README.md
  - ks:docs/sdk/agents/react/context-caching-README.md
---
# Plan tracking (react v2)

React v2 treats plans as explicit timeline artifacts.

- There is no separate persistent plan store.
- Cross-turn plan truth lives in `react.plan` blocks on the timeline.
- The per-turn runtime state only keeps a short working copy of the current plan steps/status.

## 1) What creates and updates a plan

In the current runtime, plans are created and replaced through the `react.plan` tool:

- `mode="new"`: create a fresh plan snapshot
- `mode="update"`: replace the current plan with a new snapshot
- `mode="close"`: close the latest active plan so it no longer resurfaces in later turns

Important:

- `active` is not a `react.plan` tool mode.
- “Keep the current plan active” means: do not call `react.plan`; the runtime will continue showing the latest active snapshot from the timeline.

Progress updates are separate from `react.plan` calls:

- the decision agent acknowledges step progress in `notes`
- runtime parses those marks
- runtime appends a `react.plan.ack` block
- runtime appends a new `react.plan` block for the same `plan_id` with merged status

There is also a reserved structured acknowledgement path, `react.plan_ack`, implemented in the plan tool module for future use. It is not published in the current React tool catalog yet.

Model-facing view:

- the model sees `react.notes`
- the model sees `react.plan` tool calls with `tc:` paths, `plan_id`, and stable `snapshot_ref`
- the model does **not** rely on raw rolling `react.plan` JSON snapshots or `react.plan.ack` blocks in the rendered timeline
- open plans are summarized in ANNOUNCE
- any plan snapshot can be reread through the stable alias `ar:plan.latest:<plan_id>`

## 2) Timeline model

### Plan snapshot block

Plans are persisted as JSON timeline blocks:

```text
type: "react.plan"
mime: "application/json"
path: "ar:<turn_id>.react.plan.<plan_id>"
```

A snapshot contains:

- `plan_id`
- `steps`
- `status`
- `created_ts`
- `last_ts`
- `origin_turn_id`
- `last_ack_turn_id`
- `last_ack_ts`
- `closed_ts`
- `closed_turn_id`
- `superseded_ts`
- `superseded_turn_id`
- `superseded_by_plan_id`

Stable reread handle:

```text
ar:plan.latest:<plan_id>
```

This alias resolves to the latest visible snapshot for that plan lineage, regardless of which turn originally emitted it.

### Plan acknowledgement block

Readable progress acknowledgements are also persisted:

```text
type: "react.plan.ack"
mime: "text/markdown"
path: "ar:<turn_id>.react.plan.ack.<iteration>"
```

Example:

```text
✓ 1. gather sources
… 2. draft summary
✗ 3. render chart
```

## 3) Turn-local vs cross-turn state

Inside a single turn, runtime keeps:

- `plan_steps`
- `plan_status`

This is only a working cache for the current turn.

Cross-turn behavior is driven by timeline snapshots:

- if the current turn has no in-memory `plan_steps`, runtime rehydrates them from the latest active `react.plan` snapshot on the timeline
- completed or closed plans are not rehydrated as active plans
- the latest active plan snapshot is carried forward across compaction so it is not lost when older history is summarized away
- older compacted plans are not resumed automatically, but compaction carries a lightweight history index plus stable `snapshot_ref`s so the agent can inspect them again with `react.read(...)`

So the authoritative history is the timeline, while `plan_steps` / `plan_status` are just the turn-local working copy.

## 4) Lifecycle

### Create (`mode="new"`)

`react.plan(mode="new")`:

- creates a fresh `PlanSnapshot`
- assigns a new `plan_id`
- records `origin_turn_id` and `created_ts`
- stores ordered `steps`
- starts with empty `status`

This snapshot becomes the current active plan.

### Replace / switch (`mode="update"`)

`react.plan(mode="update")` targets an existing `plan_id`.

It does two append-only things:

1. appends a terminal snapshot for the targeted old plan, marking it `superseded`
2. appends a fresh replacement plan with:
   - a new `plan_id`
   - a fresh ordered `steps` list
   - empty step status

So `update` does not mutate the old plan in place and does not leave the old plan looking unfinished forever. The newest open snapshot becomes the current plan.

### Maintain

If the current plan still applies, the agent should not call `react.plan`.

In that case:

- the latest active snapshot remains visible in ANNOUNCE
- runtime can rehydrate its `steps` on later turns
- step progress can continue through `notes` acknowledgements

### Acknowledge progress

When `notes` contains lines such as:

```text
✓ [1] gather sources
… [2] draft summary
✗ [3] render chart
```

runtime:

1. parses those markers
2. appends a `react.plan.ack` block
3. loads the latest plan snapshot
4. merges the new status marks into that snapshot
5. appends a new `react.plan` block with the same `plan_id`

So:

- explicit `update` creates a new plan snapshot
- progress acknowledgements keep updating the current snapshot lineage with the same `plan_id`

### Complete

A plan is treated as complete when all of its steps are no longer pending.

Completed plans remain in timeline history, but they are not treated as active plans in later turns.

### Close (`mode="close"`)

`react.plan(mode="close")`:

- targets an explicit `plan_id` when provided (otherwise defaults to the latest active plan)
- clears turn-local `plan_steps` / `plan_status` for that active lineage
- appends a closing `react.plan` snapshot for that `plan_id`
- records `closed_ts` and `closed_turn_id`

This is how React discards a plan without pretending it completed successfully.

After close:

- the plan remains in timeline history
- it is no longer shown as active in ANNOUNCE
- later turns do not rehydrate it as the current plan

## 5) ANNOUNCE behavior

ANNOUNCE is rebuilt every decision round from timeline state.

ANNOUNCE now shows only the last N open plans (currently 4), not every historical lineage.

For each visible open plan it shows:

- `plan_id`
- stable `snapshot_ref`
- created turn / timestamp
- last update turn / timestamp
- current step markers

Closed, complete, and superseded plans are excluded from ANNOUNCE.

## 6) What “active plan” really means

In the current React v2 runtime, “active plan” is derived, not explicitly stored as a separate mode.

It means:

- latest snapshot for that `plan_id`
- not closed
- not superseded
- not complete

That is why older plans can stay on the timeline while only one plan is resumed across turns.

## 7) Compaction and historical plans

Compaction treats plans in two different ways:

- the latest active plan is carried forward as a live `react.plan` snapshot so cross-turn continuation still works
- older compacted plans are exposed through a visible `react.plan.history` block plus stable `ar:plan.latest:<plan_id>` snapshot refs

That preserved snapshot ref is for inspection, not automatic resume.

So after compaction:

- React still resumes only one active plan automatically
- older plans stay directly reopenable with `react.read([...])` on the carried history snapshot ref
- this lets the agent assess whether an older line of work is relevant again in the same turn without waiting for a later turn

## 8) Efficiency notes

The current implementation is lightweight:

- explicit plan operations are sparse
- per-turn working state only stores the current step list and step-status deltas
- cross-turn recovery reads the latest plan snapshot from the timeline instead of maintaining a separate persistent plan cache
- if compaction would cut away the latest active plan snapshot, runtime carries that snapshot forward into the retained window

The main cost is scanning timeline plan blocks when ANNOUNCE is rebuilt or when plan history is rendered, which is usually small because plan blocks are rare compared with ordinary conversation blocks.
