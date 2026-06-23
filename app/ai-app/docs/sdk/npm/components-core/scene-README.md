---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/npm/components-core/scene-README.md
title: "Scene"
summary: "Headless scene runtime in @kdcube/components-core/scene: surface registry, context-drag broker, drop target config, surface command routing, and provider-backed object open."
status: implementation
tags: ["sdk", "npm", "components-core", "scene", "surfaces", "drag-drop", "runtime"]
updated_at: 2026-06-23
keywords:
  [
    "@kdcube/components-core/scene",
    "createSceneRuntime",
    "createContextDragBroker",
    "surface registry",
    "scene drop targets",
  ]
---

# Scene

`@kdcube/components-core/scene` contains the framework-free parts of the scene:
surface registration, target-surface command routing, context-drag brokering,
drop-target matching, and helper normalization.

The scene package does not mount iframes or fetch runtime config by itself. A
website or widget host wires those details and calls the core functions.

## Responsibilities

```text
scene host app
  loads config
  mounts iframes/components
  owns auth/runtime origins
  owns postMessage transport
        |
        v
components-core/scene
  normalizes contexts
  matches configured drop targets
  tracks active drag
  calls injected objectAction(open)
  routes returned target_surface
```

## Important Exports

| Export | Purpose |
| --- | --- |
| `createSceneRuntime` | Register surfaces and route provider-returned `target_surface` commands. |
| `createContextDragBroker` | Track one active drag and resolve attach/pin/open drops. |
| `normalizeSceneContext` | Normalize context/object-ref payloads at scene boundaries. |
| `normalizeSceneDropTarget` / drop-target helpers | Convert config into predictable drop target records. |
| host drag helpers | Browser drag helpers shared by host implementations. |

## Genericity Boundary

Allowed:

- using host config to decide candidate drop targets;
- passing full `object_ref` to an injected object-action client;
- routing returned `ui_event.target_surface` to a registered surface;
- using explicit host composition policy such as `task:*` for target hints.

Not allowed:

- interpreting what `task:`, `mem:`, `fi:`, or `conv:` means;
- deriving actions from card kind or namespace;
- declaring widget event subscriptions on behalf of components;
- building provider-specific payloads.

## Object Open

```text
drop/click object_ref
  -> scene objectAction({ action: "open", object_ref, target_surface })
  -> provider resolver validates object + target
  -> provider returns ui_event.target_surface
  -> scene sends local surface command
```

The provider response is authoritative. Drop-target config is only candidate
selection and user-interface policy.

## Related Docs

- `docs/sdk/solutions/scene/generic-scene-contract-README.md`
- `docs/sdk/solutions/scene/scene-composition-README.md`
- `docs/sdk/solutions/scene/cross-surface-context-drag-README.md`
- `docs/sdk/solutions/scene/config/README.md`

