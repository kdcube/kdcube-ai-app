---
id: ks:docs/sdk/agents/react/react-announce-README.md
title: "React Announce"
summary: "Announce block semantics and lifecycle in React v2."
tags: ["sdk", "agents", "react", "announce", "timeline"]
keywords: ["announce banner", "system signals", "plan status", "feedback"]
see_also:
  - ks:docs/sdk/agents/react/feedback-README.md
  - ks:docs/sdk/agents/react/flow-README.md
  - ks:docs/sdk/agents/react/plan-README.md
---
# ReAct Announce Block (ANNOUNCE banner)

This doc describes how the **announce** block is used for ReAct v2.

## What it is
- An **ephemeral tail block** added by the runtime for each decision round.
- Contains ANNOUNCE️:
  - iteration
  - open-plan summary with plan ids, snapshot refs, and status markers (if any exist)
  - authoritative temporal context (UTC + user timezone)
  - optional system notices (e.g., cache TTL pruning)

## Where it appears
- It is appended at the end of the timeline when `timeline(include_announce=True)` is called.
- It is **never cached**.

## Lifecycle
- During the loop: updated each round with a fresh ANNOUNCE.
- On exit: the final announce block is **persisted** into the turn log blocks,
  then announce is cleared.

## Feedback in ANNOUNCE
- Feedback updates are fetched **only at turn start** (timeline load).
- If cache is **hot**, feedback remains in ANNOUNCE each round until a cold turn incorporates it.
- If cache is **cold**, feedback is injected into the target turn(s) and ANNOUNCE shows the same updates
  once with “(incorporated into turn timeline)”.
- After incorporation, those items are **not** repeated in later turns.

## System messages in announce
When cache TTL pruning occurs, the render path appends a one-time announce block
containing a system notice. It appears after the budget section and advises
the agent to use `react.read(path)` to restore truncated context.

## Why it exists
- Keeps high‑frequency state updates out of the cached timeline.
- Allows downstream agents (final answer generator) to see the **last ℹ️ ANNOUNCE ℹ️**
  via the persisted contribution block.

## Example (open plans)
```
╔══════════════════════════════════════╗
║  ANNOUNCE — Iteration 3/15           ║
╚══════════════════════════════════════╝

[BUDGET]
  iterations  ███░░░░░░░  12 remaining
  time_elapsed_in_turn   2m15s

[AUTHORITATIVE TEMPORAL CONTEXT (GROUND TRUTH)]
  user_timezone: Europe/Berlin
  current_utc_timestamp: 2026-02-10T13:55:01Z
  current_utc_date: 2026-02-10
  All relative dates MUST be interpreted against this context.

[ACTIVE PLANS]
  - plans: 2 visible
    • plan_id=plan:turn_1:abcd1234
      snapshot_ref=ar:plan.latest:plan:turn_1:abcd1234
      created_turn=turn_1
      created_ts=2026-02-07T19:10:00Z
      last_update_turn=turn_1
      last_update_ts=2026-02-07T19:22:10Z
      ✓ [1] gather sources
      □ [2] draft report
    • plan_id=plan:turn_3:efgh5678 (current)
      snapshot_ref=ar:plan.latest:plan:turn_3:efgh5678
      created_turn=turn_3
      created_ts=2026-02-10T13:50:00Z
      last_update_turn=turn_3
      last_update_ts=2026-02-10T13:54:00Z
      □ [1] draft answer
      □ [2] verify citations
```

## Notes
- ANNOUNCE is the active plan presentation layer; React does not rely on a separate persistent `react.plan.active` tail artifact.
- Closed, complete, and superseded plans are excluded from ANNOUNCE.
- Announce is not cached and is re‑rendered each decision round.
