---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/conversation/hosted-agent-conversation-README.md
title: "Hosted-Agent Conversation Continuity"
summary: "How a wrapped external agent (LangGraph, LangChain, a raw loop) gets a continuous conversation when hosted as a KDCube app. Two memories carry the conversation and must agree: the agent's OWN working memory (its checkpointer / store — what the model sees this turn) and KDCube's platform conversation record (the durable record the chat component lists, reloads, searches, and titles). Covers the framework-neutral turn recorder (minimal turn log + timeline artifact), first-turn title generation and its identity contract, durable checkpointer keying (thread_id = conversation_id) with its dependency and loud-fallback requirements, and why the client-sent chat_history is a hint rather than the source of truth."
tags: ["sdk", "solutions", "conversation", "hosting", "langgraph", "port", "checkpointer", "turn-recorder", "conversation-record", "follow-up"]
updated_at: 2026-07-13
keywords:
  [
    "hosted agent conversation",
    "wrap external agent",
    "port langgraph to kdcube",
    "conversation continuity",
    "conversation history",
    "durable checkpointer",
    "AsyncPostgresSaver",
    "thread_id conversation_id",
    "record_minimal_turn_log_if_absent",
    "record_conversation_timeline",
    "conv.timeline.v1",
    "conversation title first turn",
    "chat.conversation.title",
    "chat_history hint",
    "follow-up steer memory",
    "langgraph-checkpoint-postgres",
  ]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/recipes/kdcube_for_agents/port-your-solution-to-kdcube-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/chat/chat-component-communication-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/events/reactive-turn-delivery-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/recipes/dataflow/connect-agentic-loop-to-ordered-delivery-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/conversation/search-README.md
---
# Hosted-Agent Conversation Continuity

When you host an external agent — a LangGraph graph, a `create_react_agent`, a
LangChain chain, a raw loop — as a KDCube app, the user experiences one
continuous conversation: they ask, get an answer, come back tomorrow, reopen the
thread, and expect the agent to remember. That continuity rests on **two
memories with two owners**, and a hosted agent works only when both are wired and
they agree.

This is the conversation-seam reference for a port. The step-by-step walkthrough
lives in the [port recipe](../../../recipes/kdcube_for_agents/port-your-solution-to-kdcube-README.md);
this page owns the continuity model the recipe points to.

## Two memories, two owners

| Memory | Owner | Holds | Powers |
| --- | --- | --- | --- |
| The agent's **working memory** | your app (framework-native) | the messages the model sees THIS turn — prior turns restored from the agent's checkpointer/store | the model's in-context recall ("repeat what you said before") |
| The platform **conversation record** | KDCube (framework-neutral) | one durable record per turn, per conversation | the chat component's list, reload, search, and title |

The two are separate stores. The conversation record is what the user sees on
screen after a reload; the working memory is what the model sees inside a turn.
A port keeps its own working memory (its store is internal and unchanged) and
lets the platform own the record. Both must reflect the same conversation.

## The platform conversation record is automatic

Every reactive turn, the platform writes the conversation record for you — no
record-writing code in your app:

- **The turn log.** If your app didn't already write a rich turn log (the React
  workflow does; a run-to-completion port does not),
  `record_minimal_turn_log_if_absent`
  (`sdk/runtime/turn_recording.py`) records a minimal one carrying the turn's
  final answer. Reload materializes the transcript from it.
- **The conversation registration.** The same call registers the conversation on
  the list via `record_conversation_timeline`, which writes the
  `conv.timeline.v1` artifact (`TIMELINE_KIND`). The conversation **list** is
  built from that artifact and only that artifact
  (`ctx_rag.list_conversations`) — the turn log alone does not make a
  conversation appear. So the timeline is written on **every** recorded turn,
  independent of whether a title exists, and it carries the title forward once
  there is one.

The delivery seam that triggers this is documented in
[reactive turn delivery](../../events/reactive-turn-delivery-README.md); the
reload contract in
[chat component communication](../chat/chat-component-communication-README.md)
("Stored Conversation Reload").

## The conversation title

A new conversation earns a short auto-title on its **first turn**. "New" is a
framework-neutral signal: the conversation has **no prior recorded turn log**
(the current turn's log is written after the turn body runs). Generate the title
with the SDK utility, emit it live so the header updates immediately, and stash
it for the recorder to persist onto the same timeline artifact:

- Generate: `generate_conversation_title(...)`
  (`sdk/tools/backends/summary/conversation_title.py`).
- Emit: `emit_conversation_title_event(...)` streams the `chat.conversation.title`
  chat event through the turn's `comm`; the chat component applies it to the
  conversation header live (a live element, independent of the answer bubble, so
  a title emitted after the answer still lands).
- Persist: return it on the turn result — the recorder writes it onto the
  `conv.timeline.v1` the list reads.

**The identity contract.** The user the recorder writes the turn under, the user
the list reads under, and the user the is-new probe reads under must be the
**same** `(user, conversation)`. When a turn runs under economics, the recording
user is the projected-authority user (`state["economics_user"]`), which can
differ from the raw actor keys — derive the is-new probe's user the same way the
recorder does, or a genuinely new conversation reads as "not new" and never gets
a title.

## The agent's working memory (the part you wire)

The model remembers only what you feed it or what its store restores. KDCube
hands the turn body the **current** user text; **prior turns come from the
agent's own memory**. For a LangGraph agent that memory is its **checkpointer**,
and three things make it durable and correct:

1. **Key `thread_id` by the platform `conversation_id`.** LangGraph restores a
   thread's messages by `thread_id`; use the conversation id (e.g.
   `f"{user_id}:{conversation_id}"`), never the session id. A session id changes
   per browser session, so keying by it means a reloaded conversation opens a
   fresh, empty thread.
2. **Make the store durable.** An in-memory saver lives only inside one process:
   its history is wiped on every restart and is absent for any conversation
   created in an earlier process (exactly the "this appears to be the start of
   our conversation" symptom on a reloaded thread). A Postgres checkpointer
   (`AsyncPostgresSaver`) persists across restarts and workers.
3. **Declare the dependency, and fall back LOUD.** The durable saver needs
   `langgraph-checkpoint-postgres` (pinned to the release compatible with the
   platform's `langgraph-checkpoint`) plus `psycopg[binary]` v3, declared in
   `requirements-chat-processor.txt` and `requirements-chat.txt`. If the saver
   can't open, degrading to an in-memory saver is acceptable **only if the
   fallback logs at WARNING** — a silent fallback turns a missing dependency into
   invisible memory loss.

If you would rather the agent mirror exactly what is on screen (rather than trust
a second store), the alternative is to reconstruct prior turns server-side from
the conversation record each turn and feed them into the agent's inputs. That
makes the platform record the single source of truth — durable across restarts,
reloads, and forks — at the cost of a reconstruction step.

## What the client sends is a hint, not the memory

The chat widget includes a `chat_history` on submit. Treat it as a convenience
signal, not the source of truth:

- It carries **user messages only** — no assistant text — so it cannot answer
  "repeat what you said."
- It is **empty on a continuation** (a follow-up or steer into an in-flight
  conversation).

Durable continuity therefore comes from the agent's own store (or the
server-side reconstruction above), not from `chat_history`.

## Follow-up and steer

Follow-up and steer are the same conversation, so they carry the same
`conversation_id` → the same `thread_id` → the agent's store restores the prior
turns. Getting the two memories right (durable store keyed by conversation id +
the platform record) is what makes follow-up, steer, and reload all "just work"
for a hosted agent.

## Checklist

- [ ] `thread_id` is keyed by the platform `conversation_id`, not the session id.
- [ ] The agent's store is durable (Postgres), with the dependency declared in the processor/chat requirements.
- [ ] Any store fallback logs at WARNING (never silent).
- [ ] The is-new probe, the recorder, and the list agree on the same `(user, conversation)`.
- [ ] The first-turn title is generated, emitted (`chat.conversation.title`), and returned on the turn result to persist.
- [ ] Verified live: a fresh conversation lists with a title, reloads with the full transcript, and — after a process restart — a follow-up still sees prior turns.
