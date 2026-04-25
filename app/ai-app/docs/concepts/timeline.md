---
id: timeline
kind: concept
name: Timeline
aliases: [conversation timeline, "conv.timeline.v1"]
category: runtime
scope: framework
related: [react_loop, sources_pool]
realized_by:
  - kdcube_ai_app.apps.chat.sdk.solutions.react.v2.browser.ContextBrowser
pitfalls:
  - Never write directly to the timeline; always go through `ContextBrowser.contribute()` so caching and ordering invariants are preserved.
  - Announce blocks are intentionally uncached — putting persistent content there guarantees it is lost between turns.
---

# Timeline

The **timeline** is the authoritative, ordered log of everything that
happened in a conversation. It is loaded at turn start, updated as the
turn progresses, and persisted at turn end as a single JSON artifact
(`artifact:conv.timeline.v1`). Every user prompt, tool call, tool result,
plan snapshot, and final completion is recorded as a discrete block.

Two block types coexist on the timeline:

- **Contribute blocks** — written via `ContextBrowser.contribute()`, saved
  to the persisted timeline, and visible in all future renders.
- **Announce blocks** — appended to the rendered tail when
  `include_announce=True`, never persisted, used for ephemeral signals
  (iteration count, budget, plan status, system notices).

The context browser inserts up to three cache checkpoints per render —
prev-turn, pre-tail, tail — enabling prefix reuse across rounds. Sources
and announce sections remain uncached every round to preserve freshness
without breaking earlier prefix stability.
