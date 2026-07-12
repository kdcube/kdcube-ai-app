---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/chat/subagent-participant-protocol-README.md
title: "Subagent Participant Protocol"
summary: "The client contract for subagent-aware chat: the envelope stamp and identity routing rule that fold a helper agent's live stream into its own thread, and the turn-triggering persona (user vs agent authorship) that names who opened each turn — live and on reload."
status: current
tags: ["sdk", "solutions", "chat", "subagents", "protocol", "client", "streaming"]
keywords:
  [
    "subagent stamp",
    "child_conversation_id",
    "subagent visibility",
    "thread routing",
    "identity fallback",
    "participant card",
    "authored_by",
    "agent_title",
    "handoff",
    "subagent.contribution",
    "subagent.converged",
    "subagent.failed",
    "forks",
    "forked_from",
  ]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/work-with-subagents-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/timeline/fork-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/chat/chat-stream-events-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/events/external-event-envelope-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/user-settings/capabilities-README.md
---
# Subagent Participant Protocol

A ReAct agent can delegate a scoped assignment to a **subagent** — a helper
agent that works in its own child conversation and reports back
([Work With Subagents](../../agents/react/work-with-subagents-README.md)
is the agent-facing contract). This page is the **client** contract: the
public envelope and record fields a chat client keys on to recognize and
render subagent-related messages. A client that implements them shows the
helper's work as its own thread and names who triggered each turn; a client
that ignores them still renders one coherent conversation stream, because
every field here is additive.

There are two client-visible surfaces:

- **The helper agent thread** — the child's live stream, folded into a
  collapsible thread anchored under the delegating turn.
- **The participant card** — the persona on a turn's triggering input:
  normally the user, and the delegating agent's helper on a continuation
  turn the helper's completion opened.

Both work identically for a live stream and for a reload, because both render
from the same source fields.

## The Subagent Stamp

Subagent traffic carries one stamp shape, everywhere it appears: as the
top-level `subagent` key on every thread-visibility live emission, and inside
the structured facts of every `subagent.*` lane event (charter, contribution,
converged/failed). One shape means a client anchors subagent traffic into
threads without parsing text.

```json
"subagent": {
  "child_conversation_id": "conv_sub_...",
  "forked_from_conversation_id": "conv_...",
  "forked_from_turn_id": "turn_...",
  "charter_goal": "...",
  "agent_title": "..."
}
```

| Field | Meaning |
|---|---|
| `child_conversation_id` | The helper's own conversation id. This is the thread key. |
| `forked_from_conversation_id` | The parent conversation the delegation was opened from. |
| `forked_from_turn_id` | The parent turn that anchors the thread. |
| `charter_goal` | A caption of the assignment, for the thread header. |
| `agent_title` | The helper's human display name, set by the delegating agent. |

## Visibility: `silent` | `thread`

How much of the child's live stream reaches the user is a per-agent config
knob, `react.agents.<id>.subagents.visibility` (default `silent`):

- **`silent`** — the child's own streaming reaches no user. The user sees the
  fork marker on the parent timeline, the contribution events, and the
  terminal outcome, all as parent-conversation context. The child conversation
  is still fully persisted and inspectable by ref and conversation id.
- **`thread`** — the child's stream is delivered live to the **parent**
  conversation's room (the user's existing socket), while the event identity
  (`conversation.conversation_id` / `turn_id`) stays the **child's**. Every
  such emission carries the top-level `subagent` stamp. This is the mode a
  thread-rendering client draws.

The visibility policy is documented agent-side in
[Work With Subagents](../../agents/react/work-with-subagents-README.md#visibility-silent--thread);
the comm-level pass-through that keeps the child's identity while addressing
the parent's room is noted in
[Comm System](../../../service/comm/comm-system.md).

## Thread Routing: Fold By Child Identity

A client folds a message into a helper thread by the child's **conversation
identity**, not by the message's marker or semantic type:

1. When the envelope carries the `subagent` stamp, route by
   `subagent.child_conversation_id`.
2. Otherwise, route by the envelope's own `conversation.conversation_id` —
   but only when it matches an **already-open thread**.

This rule is deliberately marker/sub_type-agnostic. Thinking deltas, ReAct
steps, the exec/code widget, and the `web_search` / `web_fetch` widgets all
fold into the thread by identity, so a client needs no bespoke per-widget
handling. Rule 2 is why: some child widget emissions ship **unstamped**
(they emit through a contextvar bound to the base communicator rather than the
stamping one), and the child's own conversation id on those emissions catches
them into the thread the child already opened. Main-lane traffic carries the
**parent** conversation id and never matches an open thread, so it can never
false-match into one.

A stamped emission also names its parent (`forked_from_conversation_id`); a
client viewing a different conversation drops subagent traffic whose parent is
not the open conversation. (The user socket is per-user, so another
conversation's subagent stream can arrive on it.)

### Rendering The Thread

A thread is a regular turn drawn indented. The child's stream runs through the
**same** delta/step/event pipeline as the main lane — there is no separate
subagent renderer. The thread header is:

- **title** = `agent_title` (fall back to a neutral label such as
  "Helper agent" when absent);
- **goal** = `charter_goal`;
- **status** = driven by the `subagent.*` lane events below.

### The Lane Events That Drive Status And Milestones

Four `subagent.*` events (their envelope shape is in
[External Event Envelope](../../events/external-event-envelope-README.md#subagent-events))
carry the thread's lifecycle; each carries the stamp in its facts, so it
anchors to the right thread without text parsing:

| Event | Lane | Drives |
|---|---|---|
| `subagent.charter` | child | Thread opens, status `running`. |
| `subagent.contribution` | parent | A milestone report (with contributed refs); appended to the thread. |
| `subagent.converged` | parent | Terminal success. |
| `subagent.failed` | parent | Terminal failure (with a reason). |

The semantic type rides in `payload.event.type`; the transport kind is
`external_event`. The event's human body may appear as `data.text`,
`data.report`, `data.reason`, or the nested `payload.event.text` — a client
reads whichever is present.

## The Participant Card

Every turn's triggering input renders with a **persona** — who authored the
input that opened the turn.

- **Normally the user.** The card shows "You" with the user's text and
  attachments.
- **A continuation turn opened by a helper's completion is authored by the
  agent.** When no parent turn is live to fold a `subagent.converged` /
  `subagent.failed` event, that completion promotes a parent continuation turn
  ([Work With Subagents](../../agents/react/work-with-subagents-README.md#report-back-reactcontribute-and-subagent-events)
  covers the promote-vs-fold rule). That turn was triggered by the helper, not
  the user, and its triggering input says so.

An agent-authored triggering input carries these fields:

| Field | Value |
|---|---|
| `authored_by` | `"agent"` |
| `agent_title` | The helper's display name. |
| `handoff` | The helper's own message to the delegating agent — optional. |

The `handoff` is the child's own `react.contribute` `report` (the message it
authored **to** the delegating agent), capped to one tidy line. It is the
child→parent channel, distinct from the child→user deliverable: a client shows
the handoff as the spoken line, not a slice of the final answer. When the
child made no contribution, there is no handoff and the field is omitted.

### Where The Persona Lives

The same persona is delivered on both surfaces so live and reload agree:

- **Live:** on `chat.start.data`, next to `message` — the client reads
  `authored_by` / `agent_title` / `handoff` off the turn-start envelope.
- **Reload:** on the persisted `chat:user` record for the continuation turn,
  carrying the same fields.

### Rendering Rules

- When `authored_by == "agent"` and a `handoff` is present, render
  `"<agent_title> said: <handoff>"` where "You" would go.
- When `authored_by == "agent"` with no `handoff`, render a neutral
  agent-authored line (for example, the helper's name with a plain
  "returned its result" caption).
- A helper-authored turn is **never** labeled "You", and never shows the raw
  event marker (such as `subagent.converged` or the `react.subagent` source
  id) as the persona.

## Reload Reconstruction

A client rebuilds the same threads and the same personas on reload from stored
relationship fields, through the ordinary conversation fetch — no separate
subagent endpoint. The full fetch contract is in
[Timeline Fork](../timeline/fork-README.md#client-reconstruction-the-fetch-contract);
for the participant surface, the fields are:

- Each parent turn that delegated carries
  `forks: [{child_conversation_id, charter_goal, agent_title, forked_at}]` on
  its turn record — the anchors for the threads to inline under that turn.
- Each child conversation carries a top-level
  `forked_from: {conversation_id, turn_id}` backref.
- The client fetches the child conversation through the **same** conversation
  fetch endpoint, as the same user, and inlines its turns as the thread
  anchored at the fork turn.

Live and reload agree because both render the same source: the stamp fields on
live emissions and the stored `forks` / `forked_from` / persona fields
reconstruct the identical thread and persona shape.

## Scheduling Note

A subagent turn is an ordinary fair-scheduled turn on the shipped processor
queue: its inception (`subagent.charter`) is admitted atomically with the
processor wakeup through the same gateway admission chat ingress uses, and it
runs through the same gates, throttling, and per-user capacity as any submitted
turn. There is no separate subagent scheduler, and none of the fields on this
page depend on one.
