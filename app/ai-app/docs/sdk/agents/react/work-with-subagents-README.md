---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/work-with-subagents-README.md
title: "Work With Subagents"
summary: "The charter-scoped subagent contract: react.delegate spawns a child conversation, react.contribute and subagent.* lane events carry results back."
tags: ["sdk", "agents", "react", "subagents", "delegation"]
keywords: ["react.delegate", "react.contribute", "charter", "subagent.contribution", "subagent.converged", "subagent.failed", "fork", "child conversation"]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/timeline/fork-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/micro-agents-and-subagents-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/shared-timeline-event-bus-steer-followup-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/react-tools-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/compaction-README.md
---
# Work With Subagents

A subagent is a full ReAct agent that works a scoped assignment in its OWN
conversation, opened from a parent turn. The parent stays interactive; the
subagent runs in the background under the same tenant/project/user, inherits
the parent's tool and skill configuration, and reports back through the
parent conversation's event lane. Phase 1 ships the complete spawn/report
loop with silent execution (nothing the subagent does streams to the user).

## The Contract In One Pass

```
PARENT CONVERSATION                    CHILD CONVERSATION (fresh id)

turn ...                               (seeded before the child starts)
  react.delegate(charter) ----------->   [fork: working summaries +
  fork marker block on timeline           parent's in-progress turn]
  ... parent keeps working ...            [SUBAGENT CHARTER] event
                                          (author = agent:<parent ref>)
  <---- subagent.contribution events    react rounds under the charter
        (live fold or next-turn           budget; react.contribute sends
        context)                          partial results back
  <---- subagent.converged / .failed    child timeline + workspace persist
```

## Spawn: react.delegate

`react.delegate` is available to an agent whose runtime carries a spawner
(the host workflow wires it; `react.subagents.enabled: false` in the agent's
bundle config removes it). Arguments:

- `charter` -- the assignment contract:
  - `goal` (required): what the subagent must achieve, self-contained. The
    subagent cannot ask the user or the parent questions.
  - `deliverables`: declared outputs (for example file paths it should
    produce).
  - `max_rounds`: the round budget (default 8, hard cap 30). This IS the
    child's iteration budget; reactive iteration credit is disabled on the
    child, so nothing extends it.
  - `contribute`: what to send back and when.
- `model` (optional): model override for the subagent's strong decision
  role. It must name a model from the agent's admin-allowed
  `supported_models` list; otherwise the configured subagent default
  (`react.subagents.model`) applies, and with neither the child inherits the
  parent's role models.

The tool returns immediately with a launch ticket
(`child_conversation_id`, `child_conversation_ref`, `child_turn_id`) and
records a `react.subagent.fork` marker block on the parent timeline -- the
parent model's durable knowledge of what it spawned, with the charter
summary and budget.

Guards: a subagent cannot spawn subagents (depth 1 in phase 1; the tool
refuses with `delegate_depth_limit` and the child's catalog carries no
`react.delegate` at all). A spawn failure surfaces as the tool result
(`delegate_spawn_failed`), and a child that dies later authors
`subagent.failed` -- failures are always authored, never silent.

## What The Child Opens With

The child conversation starts from a fork: a projection copy of the parent
conversation's working summaries plus the parent's in-progress turn, with
file refs conversation-qualified so they stay pullable across conversations.
The fork mechanics (ordering, ref rewriting, persistence) are the timeline
fork primitive -- see
[fork-README.md](../../solutions/timeline/fork-README.md).

After the fork, the charter arrives as an authored event on the child's own
event lane (`payload.event.type = subagent.charter`, author
`agent:conv_<parent id>/<parent turn>`), folded into the child's first turn
by the ordinary external-event fold. The charter text names the goal,
deliverables, budget, and the contribute expectation; it is the child's
task, while the forked blocks above it are context.

## Report Back: react.contribute And subagent.* Events

The child's catalog carries `react.contribute(report, refs)`:

- `report`: text written for the delegating agent.
- `refs`: logical paths from the CHILD conversation, delivered
  conversation-qualified. File refs (`conv:fi:conv_<child id>.turn_...`)
  are the working currency: the parent's `react.pull` resolves them
  directly, which is why charter deliverables are declared as files. Other
  namespaces ride along as provenance.

Each contribute call authors one `subagent.contribution` event into the
parent conversation's lane, through the same inception primitive consent
grants use: transport kind `external_event`, semantic type nested in
`payload.event.type`, `task_payload=None` and `reactive: false` -- passive by
construction, so a contribution can never start a turn or buy the parent
iteration credit. A LIVE parent turn folds it mid-flight through the lane
watcher (fold totality renders it and advances the cursor); an idle parent
receives it as context at its next turn.

At child completion the runtime authors one terminal event the same way:

- `subagent.converged` -- carries the child's final answer.
- `subagent.failed` -- carries the failure reason (budget exhausted without
  an answer, or an exception).

## Silent-v1 Visibility

The user sees exactly three things from a subagent: the fork marker on the
parent timeline, the contribution events, and the terminal
converged/failed event -- all as parent-conversation context. The child's
own streaming (thinking deltas, tool events, canvas writes) reaches no one:
the child's communicator carries a deny-all event filter at the emission
choke point, and its routing has no socket. The child conversation itself is
fully persisted (timeline, workspace artifacts, final answer), so its work
is inspectable by ref and by conversation id after the fact.

## Cost

Every subagent round is a full decision-model call billed like the parent's
own rounds, and the child starts with a cold prompt cache (the fork copies
context bytes; it cannot copy cache state -- see
[micro-agents-and-subagents-README.md](micro-agents-and-subagents-README.md)
for why any separate agent call has its own cache story). Child spend is
accounted under the CHILD conversation for the same user and app, tagged
with accounting agent/component `react.subagent` and a `subagent` metadata
block naming the parent conversation, turn, and charter goal -- so subagent
spend is separable in the ledgers. Charter discipline follows: one
well-chartered subagent beats several small ones, and quick work belongs in
the parent's own rounds.

## Choosing The Delegation Weight

Three delegation instruments, ordered by weight:

1. `llm_tools.generate_content_llm` -- one separate model call that returns
   its artifact inline to the calling turn. The degenerate no-fork case: no
   child conversation, no charter, no lane events. Right for a single
   generation with a precise handoff.
2. In-turn micro-agent calls -- separate model calls launched from within a
   turn whose results fold back into the same timeline. Their prompt-shape
   and cache economics are the subject of
   [micro-agents-and-subagents-README.md](micro-agents-and-subagents-README.md);
   everything that doc says about envelopes, handoff cost, and cache
   prefixes applies to every instrument on this list.
3. `react.delegate` -- this document: a chartered child CONVERSATION with its
   own timeline, workspace, budget, and lane-event reporting, running in
   parallel with the parent. Right for self-contained work worth its own
   budget and persistence.

The boundary: instruments 1-2 live and die inside the parent's turn;
instrument 3 outlives the turn, holds durable state of its own, and reports
through the conversation event lane.
