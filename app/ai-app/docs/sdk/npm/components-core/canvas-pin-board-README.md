---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/npm/components-core/canvas-pin-board-README.md
title: "Canvas Pin Board"
summary: "Core canvas pin-board contracts: board/card model, proxy refs, canvas ingress, card context, and the split between canvas-owned cards and provider-owned objects."
status: implementation
tags: ["sdk", "npm", "components-core", "canvas", "pin-board", "ingress", "proxy"]
updated_at: 2026-06-23
keywords:
  [
    "@kdcube/components-core/canvas",
    "CanvasBoard",
    "pin board",
    "kdcube.canvas.ingress",
    "proxy cards",
    "object_ref",
  ]
---

# Canvas Pin Board

`@kdcube/components-core/canvas` defines the headless canvas model and ingress
helpers used by the pin-board widget and React `CanvasBoard`.

The user-facing concept is the **pin board**: a desk of proxy cards. The protocol
and source modules use **canvas**.

## What Canvas Stores

Canvas owns cards, not provider objects.

```text
canvas card
  object_ref        provider-owned identity
  title/preview     cached display hints
  layout            x/y/w/h, board placement
  comments          canvas-owned user annotations
  source/provenance scene/source metadata

provider object
  schema
  data
  permissions
  lifecycle
  actions
```

Canvas must preserve `object_ref` and delegate behavior to provider resolvers.
It must not infer actions from `kind`, `namespace`, `object_kind`, or URI grammar.

## Important Exports

| Export area | Purpose |
| --- | --- |
| `canvasTypes.ts` | Board/card/context types. |
| `canvasModel.ts` | Normalize board/card data and build projections/context. |
| `contextTypes.ts` | Card/context object normalization. |
| `ingress.ts` | Build canvas card inputs from object refs, uploaded files, or text. |
| `ingressBridge.ts` | Parse/build canonical `kdcube.canvas.ingress` packets. |
| `ids.ts` | Stable canvas/card id helpers. |

## Ingress

See [Context drag](./context-drag-README.md) for the packet format.

```text
kdcube.canvas.ingress
  payload_type: object.ref
  payload.object_ref: provider-owned ref

kdcube.canvas.ingress
  payload_type: content.text
  payload.content.text: inline text canvas will host
```

`payload_type` is not a behavior key. It only selects payload shape.

## Canvas-Owned Content

Provider objects keep provider refs. Inline text or uploads that do not already
have provider refs become canvas-owned hosted objects, usually with `cnv:`
identities and display labels such as `provided.text`, `user.text`, or
`agent.text`.

Those labels are local display labels. They are not cross-surface routing signals.

## React Binding

`@kdcube/components-react/canvas` exports `CanvasBoard`. It renders and edits
boards but expects the host/widget to provide storage and resolver callbacks.

## Related Docs

- `docs/sdk/solutions/canvas/canvas-sdk-solution-README.md`
- `docs/sdk/solutions/canvas/pin-integration-README.md`
- `docs/sdk/solutions/canvas/pin-operations-README.md`
- `docs/sdk/solutions/scene/cross-surface-context-drag-README.md`
