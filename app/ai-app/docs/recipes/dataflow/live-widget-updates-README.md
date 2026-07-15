---
id: repo:kdcube-ai-app/app/ai-app/docs/recipes/dataflow/live-widget-updates-README.md
title: "Live Widget Updates"
summary: "Executable recipe for pushing server-side state changes to open widgets in real time: tenant/project broadcasts, session-routed pushes to a specific user, scene-hosted delivery, distributed emit state, and the trace path when an update goes missing."
status: active
tags: ["recipes", "dataflow", "live-updates", "project-events", "sse", "scene", "widgets", "broadcast"]
updated_at: 2026-07-16
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/bundle/bundle-transports-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/comm/client-transport-protocols-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/comm/data-bus-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/recipes/components/scene-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/scene/scene-event-orchestration-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/delegated-connections/delegated-connections-README.md
---
# Live Widget Updates

Your app changed state on the server — a cron recomputed a snapshot, an agent
updated an issue through a named service, an OAuth grant landed from another
device — and a user has a widget open that shows that state. This recipe makes
the widget move by itself, with no manual refresh.

This is a first-class app primitive. Three shipped apps use it today:

- `kdcube.stats` pushes dashboard snapshots to every open usage widget in a
  tenant/project;
- `task-tracker` nudges open task lists and the issue editor when any issue
  changes, whoever changed it;
- `connection-hub` delivers delegated-access grants and revocations to the
  open hub of exactly the affected user.

## Pick The Pattern

```text
who must see the update?
  |
  +-- every viewer in a tenant/project ........ A. project broadcast
  |     stats snapshot, task change nudge,
  |     news issue published
  |
  +-- one specific user's open widgets ........ B. session-routed push
        their OAuth grant landed, their
        long-running export finished
```

Both patterns ride the same relay: the emitter publishes to a Redis channel,
ingress fans out to connected clients over SSE. What differs is the channel
scope and who receives.

```text
bundle code (proc)                      ingress                     browser
------------------                     -------                     -------
comm.project_event(...)   --Redis-->   SSE hub: clients with       widget SSE
  channel {t}:{p}:                     project_events=true in      or scene
  chat.events.__project__              the same tenant/project     relay

relay.emit(session_id=S)  --Redis-->   SSE/Socket.IO peers of      widget's own
  channel {t}:{p}:                     session S                   authenticated
  chat.events.S                                                    connection
```

One transport fact governs the client side: **tenant/project broadcasts are
delivered over SSE only.** The Socket.IO gateway joins per-session relay
channels; it never carries `__project__` traffic. A widget (or scene host)
that wants broadcasts must hold an SSE stream opened with
`project_events=true`.

## A. Project Broadcast

Use when every viewer of the tenant/project may see the payload. Keep the
payload compact and safe for all of them — it is a nudge plus a snapshot, not
a private document.

### Emit

From a request context, `comm.project_event(...)` on the current communicator
is enough. From a **cron or any headless context**, build a purpose-built
scoped communicator — never prefer an ambient one; a leaked ambient
communicator carries another execution's scope:

```python
from kdcube_ai_app.apps.chat.emitters import (
    ChatCommunicator, ChatRelayCommunicator, PROJECT_BROADCAST_ROOM,
)

def _broadcast_comm(self) -> ChatCommunicator:
    tenant, project = self._runtime_scope()
    request_id = f"my-snapshot-{uuid.uuid4()}"
    return ChatCommunicator(
        emitter=ChatRelayCommunicator(),
        tenant=tenant, project=project,
        user_id="system", user_type="system",
        service={"request_id": request_id, "tenant": tenant,
                 "project": project, "user": "system", "bundle_id": BUNDLE_ID},
        conversation={"session_id": PROJECT_BROADCAST_ROOM,
                      "conversation_id": "my.snapshot", "turn_id": request_id},
    )

await self._broadcast_comm().project_event(
    type="my_app.snapshot",
    step="my_app.snapshot",
    status="completed",
    title="Snapshot Updated",
    agent=BUNDLE_ID,
    auto_markdown=False,
    data={"surface": "dashboard", "data_scope": {...}, "snapshot": {...}},
)
```

The `service.tenant/project` in the envelope and the communicator's
tenant/project must both carry the runtime scope — the channel name and the
hub's recipient matching are derived from them.

### Emit state is shared, never per-instance

Crons tick in every worker on every machine. A debounce timestamp or a
"changed since last emit" signature held in instance memory dedupes only
within one process — the fleet re-emits every tick. Keep that state in Redis:

```python
# one emit sweep per debounce window, across all workers and all emitting crons
acquired = await redis.set(window_key, "1", nx=True, px=debounce_ms)
if not acquired:
    return  # someone in the fleet already swept this window

# suppress unchanged snapshots fleet-wide
stored = await redis.get(sig_key)
if stored == sha256(stable_snapshot_json):
    return  # unchanged
...emit...
await redis.set(sig_key, digest, ex=SIGNATURE_TTL)
```

`kdcube.stats` implements exactly this (entrypoint
`_acquire_project_snapshot_window` / `_project_snapshot_signature_unchanged`),
with a per-instance fallback when Redis is absent and fail-open on Redis
errors — a duplicate emit beats a silently missing one.

### Receive: widget owns its stream

A standalone widget opens its runtime's shared SSE stream with the broadcast
opt-in and filters what it applies:

```ts
const url = new URL(`${baseUrl}/sse/stream`)
url.searchParams.set('stream_id', streamId)
url.searchParams.set('tenant', routeTenant)      // the widget's runtime scope
url.searchParams.set('project', routeProject)
url.searchParams.set('project_events', 'true')
const es = new EventSource(url.toString(), { withCredentials: true })
es.addEventListener('chat_service', (raw) => {
  const envelope = JSON.parse(raw.data)
  if (envelope.type !== 'my_app.snapshot') return
  // scope filter: a collector can serve several data scopes
  const scope = envelope.data?.data_scope
  if (scope && (scope.tenant !== dataTenant || scope.project !== dataProject)) return
  applySnapshot(envelope)
})
```

`tenant`/`project` on the stream are the widget's **runtime** scope (where its
iframe is served from); `data_scope` inside the payload is which dataset the
snapshot describes. The stats usage widget keeps them separate on purpose —
one collector runtime broadcasts snapshots for several data scopes and each
widget applies only its configured one.

### Receive: scene-hosted widget

Embedded in a scene, a widget does not open its own stream. It claims its
events once and the host delivers them as `postMessage`:

```ts
bindComponentEventSubscriptions({
  component: 'my_widget',
  transportMode: 'scene',
  transports: { scene: createSceneEventTransport({ logger: console }) },
  subscriptions: [{
    id: 'my_widget:snapshot',
    source: 'sse',
    events: ['my_app.snapshot'],
    channels: ['chat_service'],
    forwardType: 'kdcube-my-app-snapshot',
    includeEnvelope: true,
  }],
})
```

The scene host serves those claims from **two relay legs feeding one scene
event bus**: its authenticated Socket.IO data-bus socket for session-routed
service events, and an SSE stream with `project_events=true` for the
tenant/project broadcasts (which the socket can never carry). Both shipped
hosts do this — `website/scene-summon.js` and the workspace app scene. Host
mechanics: [Scene recipe](../components/scene-README.md) and
[Scene Event Orchestration](../../sdk/solutions/scene/scene-event-orchestration-README.md).

A widget that must work in both modes runs both paths and lets the embed
decide: own SSE only when top-level (`window.parent === window`), scene claim
always. The task-tracker widgets are the shipped example
(`ui/widgets/wizard/src/api/hostEvents.ts`).

## B. Session-Routed Push To One User

Use when the update belongs to one user: their grant landed, their export
finished. The widget already holds an authenticated session; the emitter needs
to know **which sessions** currently show the affected state.

The shipped pattern (connection-hub delegated access) is a live-session
registry plus a session-routed relay emit:

1. When the widget's authenticated context is established, the server
   registers the session against the subject it displays — a Redis ZSET keyed
   by subject, scored by expiry, pruned on read.
2. When the state changes (grant recorded, access revoked), the emitter loads
   the live sessions for that subject and emits one envelope per session:

```python
await relay.emit(
    event="chat_service",
    data=envelope,          # type: my_app.thing.changed, route: chat_service
    tenant=tenant, project=project,
    session_id=session_id,  # the registered live session
)
```

3. The widget subscribes on its own authenticated connection and refreshes on
   the event.

Walkthrough with the registry key shape and envelope:
[Delegated Connections → Live Delivery To Open Hubs](../../sdk/solutions/connections/delegated-connections/delegated-connections-README.md#live-delivery-to-open-hubs).

Session-routed envelopes travel over both SSE and Socket.IO — the session
channel is what both transports subscribe.

## The Handler Is Part Of The Feature

Delivery ends at the widget's handler, and the handler must actually apply
the change. The instructive shipped bug: the task editor received every
`task_tracker.task.changed` event, refetched the fresh issue — and its
reconcile reducer merged only the attachment list, so an agent-added tag
never rendered until reopen. The fix keeps a baseline of field values as last
loaded and adopts the server value for every field the user hasn't locally
diverged on (`task-tracker@1-0/ui/widgets/wizard/.../issueWizardSlice.ts`).

Rules that survive contact with users:

- refetch the authoritative object on the nudge instead of trusting an inline
  snapshot — change events can arrive out of order;
- reconcile in place; never close or reload an editor the user is typing in;
- an in-progress edit wins over a background change, field by field;
- display caps lie: a card that renders `tags.slice(0, 8)` shows "stale" data
  forever when the newest tag is the ninth. Cap with an overflow indicator.

## When An Update Goes Missing

Every hop has an observable. Walk them in order:

```text
1. proc log     [ChatRelayCommunicator] emit_project ... channel=...
                did the publish happen, and to which channel?
2. ingress log  [SSEHub._on_relay] project event ... recipients=N streams=[...]
                did the hub match clients? zero recipients dumps the
                registered population with scope + project_events flag
3. redis tap    PSUBSCRIBE kdcube.relay.chatbot.*
                the raw wire; message = JSON {target_sid, session_id,
                event, data, timestamp}
4. browser      host console filter "kdc-scene": scene event dispatched
                widget iframe console: its own receipt log
```

If all four pass and the UI still doesn't move, the bug is in the widget's
handler or its display path — see the previous section.

## Configuration Touchpoints

- Broadcast cadence and scope live in bundle props — e.g. stats:
  `stats.ui.project_broadcast: {enabled, cron, debounce_seconds, surfaces,
  data_scopes[]}`. A scope missing from that list is never broadcast, however
  fresh the data is on refresh.
- The widget's transport choice is scene/profile config, per widget:
  `liveEventsTransport: "sse" | "scene"` — see the
  [Scene recipe](../components/scene-README.md).
- The scene host's component entry decides which surface a widget owns; give
  each target surface exactly one owner or opens land in the wrong window.
