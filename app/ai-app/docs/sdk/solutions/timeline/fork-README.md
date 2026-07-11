---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/timeline/fork-README.md
title: "Timeline Fork"
summary: "The fork primitive: seeding a new conversation with a projection copy of another conversation's working summaries and in-progress turn."
tags: ["sdk", "solutions", "timeline", "fork", "subagents"]
keywords: ["fork", "projection", "working summary", "range summary", "conv:fi:", "conversation-qualified refs", "subagent.charter"]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/work-with-subagents-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/timeline-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/compaction-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/react-realm-refs-and-workspace-paths-README.md
---
# Timeline Fork

A fork seeds a NEW conversation with a projection copy of an existing one:
the source conversation's working summaries plus its in-progress turn become
the new conversation's pre-existing history. The copy is by value -- two
timelines share no state afterward; each persists and compacts on its own.
Phase 1's consumer is the subagent spawn
([work-with-subagents-README.md](../../agents/react/work-with-subagents-README.md)),
and the primitive itself is agnostic of who reads the fork.

Code: `kdcube_ai_app/apps/chat/sdk/solutions/react/subagents/fork.py`
(`build_fork_projection`, `qualify_file_refs`, `build_fork_marker_block`).

## The Projection

`build_fork_projection` assembles the seed blocks in this order:

1. The source conversation's latest `conv.range.summary` (when it has
   compacted). It comes FIRST because the timeline persist window starts at
   the newest range summary -- a block placed before it would be sliced away
   on the first persist.
2. A fork header block (`subagent.fork.header`) naming the source
   conversation and turn, and stating the ref rules below in model-facing
   words.
3. Every `conv.working.summary` block of the source conversation, deduped
   by path, in original order -- exactly the durable per-turn digests the
   compaction machinery keeps as blocks.
4. The source's current-turn blocks, verbatim: the prompt, tool calls and
   results, notes, attachments -- whatever the source agent could see of its
   in-progress turn.

The seed is persisted as the new conversation's timeline artifact
(`conv.timeline.v1`) BEFORE the new conversation's first turn, so the
ordinary `load_timeline` path finds it as prior history, sets the
current-turn offset after it, and appends the new turn header -- no special
load mode exists.

## Ref Semantics

Block paths in a timeline are turn-qualified (`conv:fi:turn_x.files/a.md`,
`conv:ar:turn_x...`), and resolvers read a bare ref as belonging to the
current conversation. Two rules keep copied refs live in the fork:

- `conv:fi:` paths (workspace files, resolved from storage) are rewritten
  with the source conversation's scope segment:
  `conv:fi:conv_<source id>.turn_x.files/a.md`. That is the standard
  cross-conversation form `react.pull` already resolves; the rewrite touches
  the block's `path`, `refs`, and `meta.path` fields only.
- `conv:ar:` / `conv:tc:` / `conv:ws:` / `conv:su:` paths stay bare: those
  blocks are copied INTO the new timeline, so timeline-resident resolution
  (`react.read`, `react.hide`) finds them by exact path match right there.

Block TEXT is never rewritten. A bare `conv:fi:turn_...` ref mentioned
inside copied prose therefore needs the `conv_<source id>.` segment added
before pulling -- the fork header states this to the model, with the source
conversation id spelled out.

## The Charter As First Event

The fork carries context; the assignment arrives separately, as the new
conversation's first authored event. The spawner publishes it onto the new
conversation's own event lane (transport kind `external_event`, semantic
type `subagent.charter` nested in `payload.event.type`, author
`agent:conv_<source id>/<source turn>`, targeted at the new turn) before the
timeline load; the ordinary external-event fold then materializes it inside
the first turn. Keeping charter and fork separate preserves the reading
order the child needs -- history first, task last -- and gives the charter the
full event-lane provenance (sequence, author, timestamp) instead of being
one more copied block.
