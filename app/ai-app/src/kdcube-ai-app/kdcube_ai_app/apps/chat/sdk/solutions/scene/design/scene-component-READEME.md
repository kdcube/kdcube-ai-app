---
id: repo:kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/scene/design/scene-component-READEME.md
title: "Reusable Scene Component Design"
summary: "Design for extracting the reusable scene orchestration kernel from bundle scenes and website pages without making layout, chrome, or branding reusable by accident."
status: draft
updated_at: 2026-06-15
tags: ["sdk", "scene", "component", "postmessage", "widgets", "surface-registry", "named-services"]
---

# Reusable Scene Component Design

The scene is not primarily a visual component. It is a UI orchestrator.

The reusable SDK unit should therefore be a headless scene runtime plus thin
adapters, not a copied website page or a copied React scene. The website
landing page, a bundle main UI, and a bundle widget that behaves as a local
scene can share the same routing logic while still owning different layout,
chrome, CSS, branding, and authentication entrypoints.

## Problem

Today we have at least two scene-like hosts:

- the versatile bundle scene in
  `sdk/examples/bundles/versatile@2026-03-31-13-36/ui/scene`;
- the public website scene in `/Users/elenaviter/src/kdcube/website/index.html`
  with its broker in `/Users/elenaviter/src/kdcube/website/scene-summon.js`
  and `scene-e.html` kept as a mirror.

Both perform the same kind of orchestration:

```text
child widget emits intent/action
  -> host validates origin/source
  -> host resolves target surface
  -> host opens/focuses/mounts target app/widget
  -> host sends command to that surface
```

The page layout cannot be shared cleanly. The orchestration can.

## Vocabulary

```text
effect
  Provider-owned object action selected for a concrete ref.
  Example: default_open_effect_action = "open" or "download".

reaction
  Scene-owned UI outcome after an effect result is known.
  Example: open task wizard, focus memory widget, download locally,
  report target_surface_unavailable.

surface
  A scene-registered UI endpoint, usually an iframe/widget/app area.
  Example: task_tracker.issue_editor, sdk.memory.viewer.

intent
  A postMessage or host event emitted by a child widget.
  Example: kdcube-object-open, kdcube.context.attach, kdcube-widget-view.
```

The important split is:

```text
Provider/resolver owns:  "what object effect should a generic click run?"
Scene owns:              "what UI reaction happens for the effect result?"
Widget owns:             "how the user initiates the intent from its UI"
```

## Target Shape

```text
@kdcube/scene-runtime
  Headless TypeScript module:
    - surface registry
    - object-open dispatcher
    - postMessage broker
    - runtime CONFIG handshake helper
    - origin/source validation
    - pending command queue and ready-flush
    - route adapters for known protocol messages

@kdcube/scene-react
  Optional React adapter:
    - useSceneRuntime()
    - SceneProvider
    - iframe refs and lifecycle helpers
    - panel/window adapter interfaces

host page or bundle scene
  Owns:
    - CSS, branding, layout, rails, windows
    - auth/login UI
    - exact iframe mount points
    - app/widget route strings
    - which surfaces are available in this composition
```

The reusable runtime should be headless because the same routing kernel must
work in:

- a React bundle scene;
- a vanilla website page;
- a nested bundle widget that orchestrates its own local child widgets;
- a host app that embeds KDCube widgets without using our visual chrome.

## Core Flow: Context Chip Opens Task Issue

```text
User clicks chat context chip
        |
        v
Chat widget calls canvas_object_action(capabilities, object_ref)
        |
        v
Provider returns:
  Provider.object_ref
  Provider.capabilities
  Provider.default_open_effect_action = "open"
        |
        v
Chat widget runs canvas_object_action(open, Provider.object_ref)
        |
        v
Provider returns:
  Provider.ui_event.target_surface = "task_tracker.issue_editor"
  Provider.ui_event.issue_id
  Provider.object payload
        |
        v
Chat widget emits postMessage:
  kdcube-object-open(response=Provider.response, source=Chat.context_chip)
        |
        v
Scene runtime validates source and dispatches by target_surface
        |
        v
Host adapter opens/focuses Task Editor and sends:
  kdcube-task-tracker-wizard-command(action=open, issue_id=Provider.issue_id)
```

There is no task-specific code in the chat component. There is no generic
"task namespace means task wizard" rule. The provider chose the effect, and
the scene reacted to the returned surface.

## Runtime API Sketch

```ts
export interface SceneRuntimeConfig {
  origin: string
  tenant: string
  project: string
  apps: Record<string, string>
}

export interface SceneSurfaceRegistration {
  surface: string
  label: string
  ensureOpen: () => void
  postCommand: (command: unknown) => boolean
  commandFromOpen: (request: SceneOpenRequest) => unknown | null
}

export interface SceneRuntime {
  registerSurface(registration: SceneSurfaceRegistration): () => void
  dispatchObjectOpen(message: KdcubeObjectOpenMessage): SceneDispatchResult
  routeMessage(event: MessageEvent): boolean
  postConfigResponse(event: MessageEvent, identity: string): boolean
}
```

The runtime should not import React. It should not know about website rails,
floating windows, or bundle panel components.

## Adapter Contracts

### DOM/Website Adapter

The website adapter provides:

```text
mountFrame(alias, parentElement)
openFloatingWindow(alias)
closeFloatingWindow(alias)
setFloatingWindowView(alias, expanded)
postFrame(alias, command)
```

This adapter can live in the website repo until stabilized, then move into SDK
as a vanilla DOM adapter if it proves broadly useful.

### React Bundle Adapter

The React adapter provides:

```text
useSceneRuntime(config)
useSceneSurface(surfaceRegistration)
useIframeSurface(alias, route, options)
```

The host component still controls JSX and CSS. The runtime only supplies
callbacks and state needed to route commands.

### Nested Scene Adapter

A widget can be a local scene for its own children. When it cannot satisfy a
target surface locally, it forwards the same normalized intent upward:

```text
nested scene
  -> dispatch local if target_surface is local
  -> otherwise parent.postMessage(kdcube-object-open, ...)
```

Only the top-level host can open sibling iframes or global overlays.

## Surface Registry

The surface registry is the scene's central table.

```text
surface id                   reaction adapter
---------------------------  --------------------------------------------
sdk.memory.viewer            open/focus memory widget, send memory command
task_tracker.issue_editor    open/focus task wizard, send issue command
task_tracker.issue_list      open/focus task list, send list command
conversation.viewer          focus chat, load conversation
```

Registration belongs to the composition, not to chat/canvas. This lets a
different host map the same `target_surface` to a different visual reaction
without changing provider or widget code.

## Message Families

The runtime should normalize these families:

```text
CONFIG_REQUEST / CONFIG_RESPONSE
  child widget asks for runtime config.

kdcube-widget-view
  child asks host to switch compact/expanded view.

kdcube-object-open
  child has already resolved an open effect and asks scene to react.

kdcube.context.attach
  host attaches a context object to chat.

kdcube-pinboard-open
  pinboard forwards a resolver-open result to host.

domain widget commands
  kdcube-task-tracker-wizard-command
  kdcube-memory-widget-command
  ...
```

Domain widget commands are not invented by the scene runtime. They are the
surface adapter's output.

## Named Services Integration

Named-service providers participate through resolver/action contracts:

```text
object.resolve
  returns object_ref, object_kind, capabilities, default_open_effect_action

object.action(action=open)
  returns ui_event.target_surface and enough payload for that surface

object.action(action=download)
  returns content_base64, filename, mime
```

The scene runtime must not infer `default_open_effect_action` from namespace,
card kind, or broad capabilities. It only reacts after a widget or resolver has
returned an explicit effect result.

## Error Handling

The runtime should produce bounded dispatch results:

```ts
type SceneDispatchResult =
  | { ok: true; message?: string }
  | { ok: false; code: string; message: string }
```

Expected errors:

```text
origin_not_allowed
message_source_not_registered
target_surface_missing
target_surface_unavailable
surface_command_rejected
surface_command_timeout
```

The visual host decides whether that becomes a toast, banner, console warning,
or no-op.

## Extraction Plan

1. Define shared TypeScript protocol types for scene messages and dispatch
   results.
2. Extract a headless `createSceneRuntime()` from the versatile scene and
   website broker behavior.
3. Move surface registration and pending-command queue into the runtime.
4. Keep visual opening/floating/window behavior behind adapter callbacks.
5. Refactor versatile React scene to call the runtime.
6. Refactor website `scene-summon.js` to call the runtime through a DOM
   adapter.
7. Add tests for:
   - object-open dispatch by `target_surface`;
   - unknown target surface;
   - pending command flush after iframe readiness;
   - origin/source validation;
   - nested-scene forward-to-parent behavior.

## Non-Goals

- Do not make the website page itself reusable.
- Do not move provider semantics into the scene.
- Do not make chat or canvas know task/memory/widget internals.
- Do not use namespace-pattern declarations as a replacement for provider
  resolver functions.
- Do not require React for the headless runtime.

## Documentation Links

- `app/ai-app/docs/sdk/solutions/chat/chat-widget-solution-README.md`
- `app/ai-app/docs/sdk/solutions/scene/scene-composition-README.md`
- `app/ai-app/docs/sdk/solutions/scene/scene-surface-registry-README.md`
- `app/ai-app/docs/sdk/namespace-services/providers-README.md`
- `app/ai-app/docs/sdk/namespace-services/clients-README.md`
