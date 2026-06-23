---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/npm/components-core/context-drag-README.md
title: "Context Drag"
summary: "Core browser contracts for moving object refs and text into scene surfaces: context drag envelopes, canvas ingress packets, and the boundary between source widgets, scene hosts, pin board, and provider resolvers."
status: implementation
tags: ["sdk", "npm", "components-core", "context-drag", "canvas-ingress", "scene", "pin-board"]
updated_at: 2026-06-23
keywords:
  [
    "kdcube-context-drag-start",
    "kdcube.canvas.ingress",
    "payload.object_ref",
    "payload.content.text",
    "canvas ingress",
    "context drag",
  ]
---

# Context Drag

Context drag is the browser-side protocol for moving a reference or piece of
content between app surfaces. It is used by chat chips, pin-board cards, memory
rows, task rows, search results, and provider widgets.

There are two related contracts:

| Contract | Purpose |
| --- | --- |
| Context drag | Move an existing object ref to another surface, usually for attach/open/pin. |
| Canvas ingress | Place an object ref or inline text onto the pin board. |

## Context Drag Envelope

The scene host listens for transient browser messages:

```text
kdcube-context-drag-start
kdcube-context-drag-end
```

The important value inside the payload is the canonical object ref:

```json
{
  "type": "kdcube-context-drag-start",
  "contexts": [
    {
      "id": "mem:record:mem_123",
      "ref": "mem:record:mem_123",
      "object_ref": "mem:record:mem_123",
      "label": "Memory",
      "title": "Excel/openpyxl charts rule"
    }
  ]
}
```

Rules:

- `ref` / `object_ref` is the identity. Hosts may normalize aliases at the
  boundary, but provider behavior must use the full object ref.
- Source widgets may include display hints.
- Scene hosts may use configured compatibility policy to show candidate targets.
- On open/drop, the scene calls provider `object.action(open, object_ref,
  target_surface)`.

## Canvas Ingress Packet

Canvas ingress is the canonical packet for placing something on the pin board.
The packet type is:

```text
kdcube.canvas.ingress
```

Object-ref payload:

```json
{
  "type": "kdcube.canvas.ingress",
  "payload": {
    "object_ref": "task:issue:ticket_2026_06_23",
    "title": "Cancel membership",
    "preview": "ticket_2026_06_23 - open",
    "presentation": {
      "label": "task",
      "namespace": "task",
      "object_kind": "task:issue"
    }
  }
}
```

Text payload:

```json
{
  "type": "kdcube.canvas.ingress",
  "payload": {
    "title": "Selection",
    "content": {
      "mime": "text/markdown",
      "text": "Selected text to place on the canvas."
    }
  }
}
```

Rules:

- `payload.object_ref` means "pin this existing provider object".
- `payload.content.text` means "host this provided text on the canvas".
- `presentation` is cosmetic and optional.
- The scene host may stamp `payload.source` from its component registry:
  `surface_ref`, `component`, `app`, `runtime`, `tenant`, `project`.
- The pin board stores a proxy card and preserves provider `object_ref`.
- Actions come from provider resolvers, not from `kind`, `namespace`, or
  presentation fields.

## Flow

```text
source widget
  creates context drag or kdcube.canvas.ingress
        |
        v
scene host
  tracks active browser drag
  stamps source metadata
  draws overlays / pulses rails
        |
        v
target surface
  chat attach
  pin-board ingress
  provider open
        |
        v
provider resolver
  owns object.action / capabilities / UI event
```

## Source Files

- `npm/packages/components-core/src/canvas/ingressBridge.ts`
- `npm/packages/components-core/src/canvas/ingress.ts`
- `npm/packages/components-core/src/scene/hostDrag.ts`
- `npm/packages/components-core/src/scene/dropTargets.ts`
- `npm/packages/components-core/src/scene/runtime.ts`

## Related Docs

- `docs/sdk/solutions/scene/cross-surface-context-drag-README.md`
- `docs/sdk/solutions/canvas/pin-integration-README.md`
- `docs/sdk/solutions/scene/config/README.md`
