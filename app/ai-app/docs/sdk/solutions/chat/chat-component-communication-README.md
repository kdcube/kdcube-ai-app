---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/chat/chat-component-communication-README.md
title: "Chat Component Communication"
summary: "Schematic map of the reusable KDCube chat component, including the headless engine, React widget, iframe host bridge, chat ingress/stream, app operations, and the boundary between conversation events and Data Bus."
status: draft
tags: ["sdk", "solutions", "chat", "component", "widget", "communication", "event-bus", "external-events", "iframe", "sse"]
updated_at: 2026-06-23
keywords:
  [
    "chat component communication",
    "chat widget communication",
    "chat event bus",
    "external_events",
    "sse chat",
    "sse stream",
    "chat_service",
    "chat host bridge",
    "postMessage",
    "Data Bus boundary",
  ]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/ecosystem-component/components-ecosystem-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/chat/chat-widget-solution-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/chat/chat-stream-events-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/events/external-events-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/events/external-events-journey-and-handling-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/comm/conversation-event-bus-and-data-bus-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/scene/scene-composition-README.md
---
# Chat Component Communication

This article describes the **chat component**: the reusable chat engine,
React chat UI, and iframe widget wrapper. It does not describe a domain widget
such as a task list, memory browser, canvas board, or news tile.

The main rule:

```text
Normal chat uses the conversation event lane and the chat stream.
Normal chat does not use Data Bus.
```

Data Bus can still be used by app tools, named services, or sibling domain
widgets, but it is not the path for sending a user message or receiving the
assistant stream in the chat component.

## Components

```text
host page / scene
  owns iframe placement, login prompt, object-open routing, cross-widget drag
  |
  | postMessage
  v
chat iframe widget
  package host bridge
  React chat UI
  @kdcube/components-react/chat
  |
  v
headless chat engine
  @kdcube/components-core/chat
  Redux state + reducers
  event batch builder
  HTTP/SSE transport
  |
  v
chat backend
  /sse/stream  -> live chat envelopes
  /sse/chat    -> submit external_events[] batches
  /api/cb/...  -> stored conversations, feedback, delete
  /api/integrations/bundles/.../operations/... -> app object actions, preview
```

The iframe wrapper is only an adapter. It maps host `postMessage` commands into
engine calls and maps engine host events back into `postMessage`. The chat
engine itself is the source of the conversation state model.

## Runtime Shape

```text
@kdcube/components-core/chat
  protocol.ts        envelope and request/response shapes
  eventBatch.ts      typed text/files/context -> external_events[]
  transport/sse.ts   EventSource /sse/stream
  transport/client.ts
                    /sse/chat submit, conversation APIs, feedback,
                    object actions, download, dry-run preview
  reducers.ts        chat_start/chat_delta/chat_step/... -> ChatState
  engine.ts          boot, auth/profile, stream lifecycle, queued sends

@kdcube/components-react/chat
  ChatStoreProvider  boots the engine
  useChatEngine      exposes state and actions to React UI
  Chat               default React view

sdk://solutions/chat/ui/widget
  packageEngine.tsx  iframe host bridge around the package engine
  host.ts            postMessage contract helpers
```

## Bootstrap

The chat component starts by resolving runtime config and identity, then opening
the chat stream when the user is authenticated.

```text
iframe loads
  |
  | host may post config/tokens
  v
settings/runtime
  |
  | fetch profile/session
  v
chat engine
  |
  | authenticated?
  |   yes -> EventSource /sse/stream
  |   no  -> disconnected, composer can request host login
  v
chat stream is ready
```

Important fields:

| Field | Owner | Meaning |
| --- | --- | --- |
| `tenant`, `project`, `bundleId` | host/runtime config | Scope for chat and app operations. `bundleId` is the protocol field name. |
| `sessionId` | profile endpoint / stream setup | User session id used by `/sse/stream`. |
| `streamId` | chat engine | Client stream id passed to `/sse/stream` and `/sse/chat`. |
| `conversationId` | backend response / stored conversation | Conversation being viewed or continued. |
| `turnId` | backend response / stream envelopes | Current or queued turn id. |

## Submit Path

The composer never sends plain free-form text by itself. It builds an ordered
`external_events[]` batch. Context chips, typed text, and attachments are
separate events in one batch.

```text
user presses Send
  |
  v
chat engine snapshots composer state
  |
  | typed text       -> event.user.prompt / event.user.followup / event.user.steer
  | files            -> event.user.attachment.file
  | context chips    -> event.external / event.canvas / event.canvas.focus / event.snapshot
  v
external_events[] batch
  |
  | POST /sse/chat?stream_id=<streamId>
  | JSON body or multipart when files are present
  v
chat ingress
  |
  | writes accepted events into conversation external-event lane
  | creates/continues conversation turn
  | returns conversation_id, turn_id, continuation metadata
  v
chat engine records local submit ack
```

Schematic body:

```json
{
  "tenant": "demo-tenant",
  "project": "demo-project",
  "bundle_id": "versatile@...",
  "conversation_id": "optional-existing-conversation",
  "active_turn_id": "only for in-turn followup/steer",
  "target_turn_id": "only for in-turn followup/steer",
  "target": {
    "agent_id": "main",
    "surface": "chat_chat",
    "story_kind": "general_chat",
    "conversation_role": "main",
    "event_source_id": "chat.main.chat.user"
  },
  "external_events": []
}
```

The exact `event_source_id` values are configurable by the mounted widget
profile. The chat component owns the packaging; the app owns the policies
that interpret those event sources.

## Stream Path

The chat component receives live backend events on the chat stream. In the
current package engine this is SSE:

```text
EventSource /sse/stream
  |
  | events:
  |   chat_start
  |   chat_delta
  |   chat_step
  |   chat_complete
  |   chat_error
  |   conv_status
  |   chat_service
  v
chat reducers
  |
  | update turns, timeline, steps, files, links, artifact surfaces, banners
  v
React chat UI
```

`chat_delta` carries streaming text. Its `delta.marker` determines the client
surface:

| `delta.marker` | Client meaning |
| --- | --- |
| `answer` | Assistant answer timeline block. |
| `thinking` | Reasoning/thinking timeline entry. |
| `timeline_text` | Timeline-only note, not an Artifacts tab object. |
| `canvas` | Canvas artifact surface plus timeline entry. |
| `subsystem` | Structured subsystem artifact such as web search, named-service search, web fetch, or code execution. |

`chat_step` carries completed structured steps such as citations, files,
accounting, followups, and service-level notices.

## Stored Conversation Reload

Reload does not replay the live stream. It fetches stored conversation artifacts
and hydrates them into the same `ChatState` model.

```text
loadConversation(conversation_id)
  |
  | POST /api/cb/conversations/{tenant}/{project}/{conversation_id}/fetch
  | body: { "materialize": true }
  v
stored turn artifacts
  |
  v
hydrateHistoricalConversation()
  |
  | chat:user rows             -> user message/additional user messages
  | chat:assistant rows        -> answer timeline blocks
  | chat.files/events/artifacts-> FileArtifact(surface=files)
  | citations                  -> LinkArtifact(surface=links)
  | named_service.search_results -> NamedServiceSearchArtifact(surface=artifacts)
  | timeline_text              -> TimelineArtifact(surface=timeline)
  v
same visible chat state
```

The same UI-surface rule applies to live and reloaded turns:

```text
surface=timeline   -> Timeline/chat feed
surface=artifacts  -> Artifacts tab
surface=files      -> Files tab
surface=links      -> Links tab
```

## Iframe Host Bridge

The iframe bridge is UI coordination only. It is not the chat transport.

Inbound messages:

```text
host -> chat iframe

{ type: "kdcube-set-view", view: "compact" | "expanded" }
{ type: "kdcube-chat-widget-command", action: "load-conversation", conversation_id }
{ type: "kdcube-auth-changed" }
{ type: "kdcube.context.attach", contexts: [...] }
{ type: "kdcube.context.focus", contexts: [...] }
{ type: "kdcube.context.remove", ids: [...] }
```

Outbound messages:

```text
chat iframe -> host

{ type: "kdcube-widget-view", widget, view }
{ type: "kdcube-auth-required", widget }
{ type: "kdcube-object-open", widget, response, source }
{ type: "kdcube-pin-conversation", conversation_id, context, contexts }
{ type: "kdcube-context-drag-start", context, contexts }
{ type: "kdcube-context-drag-end", ...point }
```

The host owns window placement, z-order, login UI, and cross-widget routing.
The chat iframe owns only the chat UI state inside its frame.

## Context Objects

Context chips are not text concatenated into the prompt. They are separate
objects that become separate external events when the user sends.

```text
host/canvas/memory/task/search result
  -> generic context envelope
  -> composer chip
  -> external event in submit batch
  -> event policy renders model-visible context
```

The generic context envelope is:

```json
{
  "type": "kdcube.context.attach",
  "contexts": [
    {
      "id": "<canonical-object-ref>",
      "kind": "<producer-declared-context-kind>",
      "label": "Visible object label",
      "ref": "<canonical-object-ref>",
      "event_source_id": "<producer-declared-event-source>",
      "surface": "<producer-declared-surface>",
      "data": {}
    }
  ]
}
```

The chat component does not hardcode memory, task, canvas, or custom object
semantics. It normalizes the object ref and asks the app resolver when the
user clicks a chip.

## Object Actions And Downloads

Opening or downloading a context chip is resolver-backed:

```text
user clicks context chip
  |
  v
chat engine calls app operation canvas_object_action(action="capabilities")
  (current compatible operation name for the generic object-action facade)
  |
  v
resolver returns default_open_effect_action
  |
  | download -> object.action("download") -> browser download
  | open     -> object.action("open") -> host kdcube-object-open
```

The chat component does not decide that `mem:`, `task:`, `cnv:`, or `conv:fi:` means
open or download. The concrete resolver response declares the effect.

## Dry Run Preview

Dry run uses the same event batch builder but does not submit a turn:

```text
composer state
  -> external_events[]
  -> POST app operation react_context_preview
  -> preview of rendered ReAct context
```

This is an app operation, not a Data Bus path.

## Data Bus Boundary

Do not describe ordinary chat as Data Bus.

```text
Chat component normal path:

  send     -> /sse/chat -> conversation external-event lane
  receive  -> /sse/stream chat_* / conv_status / chat_service envelopes

Not this:

  send chat -> data_bus.publish
```

Socket.IO transport code can expose `data_bus.publish` for hosts that need
domain-message publishing, and app tools may use Data Bus internally for
ordered domain mutations. That is separate from the chat component's normal
send/stream path.

## Compact End-To-End View

```text
Host/Scene
  | postMessage: config, context attach, view commands
  v
Chat iframe widget
  | React UI + host bridge
  v
Chat engine
  | build external_events[]
  | POST /sse/chat
  v
Ingress + conversation external-event lane
  | accepted events -> turn processing
  v
ReAct/app runtime
  | emits chat_start/chat_delta/chat_step/chat_complete
  v
/sse/stream
  |
  v
Chat reducers -> ChatState -> rendered chat UI
```

## What To Check When Debugging

| Symptom | Check |
| --- | --- |
| Send button does nothing | Composer has text/files/context; user is authenticated or host handles `kdcube-auth-required`. |
| Submit accepted but no stream | `/sse/stream` is connected and `stream_id` matches `/sse/chat`. |
| Context appears as text | Producer sent generic context envelope incorrectly or omitted a canonical ref. |
| Timeline notes appear in Artifacts | Client artifact projection should keep `TimelineArtifact.surface="timeline"`. |
| Files missing after reload | Stored artifacts must include explicit file surfaces (`chat.files` / declared files), not incidental `mime` fields. |
| Someone calls it Data Bus | Verify whether the path is `/sse/chat` + `/sse/stream` (chat) or `data_bus.publish` (domain bus). |
