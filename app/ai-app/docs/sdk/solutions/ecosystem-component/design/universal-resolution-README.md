---
id: docs/sdk/solutions/ecosystem-component/design/universal-resolution-README.md
title: "Universal Object Resolution"
summary: "Design boundary for resolving ecosystem object refs: centralized URI routing may choose owner resolvers, but scene/canvas/chat behavior must not be hardcoded from namespace prefixes."
status: design
tags:
  [
    "sdk",
    "solutions",
    "ecosystem-component",
    "design",
    "named-services",
    "object-resolution",
    "scene",
    "canvas",
    "uri",
  ]
updated_at: 2026-06-23
see_also:
  - docs/sdk/namespace-services/README.md
  - docs/sdk/namespace-services/providers-README.md
  - docs/sdk/namespace-services/integration-README.md
  - docs/sdk/solutions/event-hub/resolver-and-policy-registration-README.md
  - docs/sdk/solutions/scene/generic-scene-contract-README.md
  - docs/sdk/solutions/scene/config/README.md
  - docs/sdk/solutions/canvas/pin-integration-README.md
---
# Universal Object Resolution

This document defines the design boundary for resolving ecosystem object refs.
The goal is not to remove all URI inspection from the system. The goal is to keep
URI inspection centralized and provider-owned, while removing namespace-specific
behavior from scene, canvas, chat, and other UI hosts.

## Core Assessment

`namespace_for_ref` in the backend resolver router is mostly acceptable. It exists
because the backend needs a cheap dispatch key to select the likely owner resolver
for a URI-like object ref.

```text
object_ref = mem:record:...
        |
        v
central resolver router
  extracts private dispatch key: mem
        |
        v
registered mem resolver
  receives the full object_ref
  parses and handles it as owner
```

This is still generic if it stays private to the resolver router. It is not
canvas learning memory or task semantics. It is closer to HTTP routing by path
prefix: the router chooses a handler, but the handler owns semantics.

The less-clean part is when scene/UI uses namespace patterns as product behavior:

```json
{
  "accepts": { "open": ["mem:*"] }
}
```

```json
{
  "accepts": { "open": ["task:*"] }
}
```

```json
{
  "providerOpen": { "patterns": ["conv:*"] }
}
```

That is config-driven, but it still means the website host understands object
families. It is acceptable as a transitional host composition policy, not as the
final ecosystem contract.

## Why Backend Namespace Routing Exists

Backend namespace routing exists for practical reasons:

- fast local resolver selection;
- avoiding N provider calls for every `object.action`;
- useful logs such as `namespace=mem` or `namespace=task`;
- stable `not_registered` responses when no owner is registered;
- compatibility with current named-service discovery, which is namespace-keyed.

As a backend router primitive, this is a reasonable optimization and still generic
enough.

## Why Naive Provider Fan-Out Is Wrong

Asking every provider directly on every UI gesture would hurt performance and make
the UI less predictable.

Bad version:

```text
drag starts
  for each target surface
    ask every provider:
      can you open this object here?
```

This is expensive and noisy, especially during hover/drag where events are
frequent. It creates unnecessary backend traffic and makes UI responsiveness
depend on resolver latency.

Better current version:

```text
hover
  use cheap generic accept mode:
    provider-open
    context
    ingress

drop
  call object.action(open, object_ref, target_surface)
  provider returns ui_event or rejects
```

Better future version:

```text
startup/cache
  scene loads resolver directory / surface compatibility claims

hover
  use cached provider-owned compatibility hints

drop
  still call object.action(open, object_ref, target_surface)
```

The drop-time resolver call remains authoritative even when hover uses cached
compatibility hints.

## Current State

Backend resolver routing:

- acceptable;
- centralized;
- does not by itself violate genericity;
- could become cleaner if resolver registration supported `matches_ref(full_ref)`
  and namespace dispatch became one built-in matcher rather than the primary
  public model.

Website scene config:

- not fully clean;
- explicit `conv:*`, `mem:*`, and `task:*` patterns are host-side object-family
  knowledge;
- should move toward provider/surface compatibility claims or drop-time
  `object.action(open, object_ref, target_surface)` decisions.

Canvas and chat:

- should treat object refs as opaque;
- may show provider-supplied or config-supplied presentation;
- must not derive behavior from `kind`, `namespace`, `object_kind`, or URI prefix.

## Allowed Boundary

Allowed:

```text
central resolver router
  may inspect object_ref privately to choose an owner resolver

owner resolver
  may parse the full object_ref however its namespace owns

scene host
  may use config to select cheap candidate drop targets
  must call provider object.action for authoritative behavior

canvas
  may preserve object_ref and cached presentation hints
  must delegate actions to resolver/provider callbacks
```

Not allowed:

```text
scene code
  if object_ref starts with "mem:" then open memories

canvas code
  if kind == "task" then show task actions

chat code
  if namespace == "conv" then route to chat conversation

host code
  building provider-specific payloads from URI grammar
```

## Target Rule

Keep this:

```text
central resolver router may inspect object_ref to choose owner
owner resolver parses object_ref
```

Remove this over time:

```text
website / canvas / chat deciding behavior from mem:* / task:* / conv:*
```

The next cleanup is therefore not "remove all namespace extraction everywhere."
The next cleanup is:

```text
keep URI routing centralized
move compatibility and action decisions to:
  provider-owned resolvers
  provider/surface compatibility claims
  cached resolver directory data
```

## Desired Contract

Components, scenes, and canvas should pass the full object ref:

```json
{
  "object_ref": "task:issue:ticket_2026_06_23",
  "action": "open",
  "target_surface": "task_tracker.issue_editor"
}
```

The resolver/provider returns the behavior:

```json
{
  "ok": true,
  "object_ref": "task:issue:ticket_2026_06_23",
  "presentation": {
    "label": "task",
    "object_kind": "task:issue",
    "color": "#2563eb"
  },
  "capabilities": {
    "open": true,
    "download": false
  },
  "ui_event": {
    "target_surface": "task_tracker.issue_editor",
    "action": "open",
    "object_ref": "task:issue:ticket_2026_06_23"
  }
}
```

The UI may render `presentation`, but behavior comes from `capabilities` and
`ui_event`, not from local URI parsing.

## Migration Path

1. Keep backend `namespace_for_ref` private to the resolver router.
2. Ensure resolver APIs always receive the full `object_ref`.
3. Make scene/canvas/chat call resolver/provider callbacks for authoritative
   actions.
4. Replace host namespace patterns with provider/surface compatibility claims.
5. Cache compatibility claims for hover/drag responsiveness.
6. Keep drop-time `object.action` authoritative even when cached hints are used.
