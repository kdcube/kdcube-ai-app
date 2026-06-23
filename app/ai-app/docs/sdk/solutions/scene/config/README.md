---
id: docs/sdk/solutions/scene/config/README.md
title: "Scene Configuration Examples"
summary: "Frontend and backend config examples for composing a generic scene from apps, surfaces, named services, events, and runtime scopes."
status: draft
tags: ["sdk", "solutions", "scene", "configuration", "apps", "named-services", "event-bus", "data-bus"]
updated_at: 2026-06-23
see_also:
  - docs/sdk/solutions/scene/generic-scene-contract-README.md
  - docs/sdk/solutions/scene/scene-composition-README.md
  - docs/sdk/solutions/scene/scene-event-orchestration-README.md
  - docs/sdk/namespace-services/README.md
  - docs/sdk/solutions/ecosystem-component/components-ecosystem-README.md
---
# Scene Configuration Examples

This folder holds concrete config examples for a website or app that composes a
KDCube scene.

Files:

| File | Purpose |
| --- | --- |
| [`website-scene.config.example.json`](website-scene.config.example.json) | Browser-side scene config: runtimes, components, target surfaces, drop targets, object-action gateway, namespace presentation, and command contracts. |
| [`backend-bundles.yaml.example`](backend-bundles.yaml.example) | Backend runtime config shape needed by the apps that participate in the scene: widgets, named-service providers/clients, ReAct event sources, canvas resolvers, Event Bus producers, Data Bus operations, and cron jobs. |

These examples intentionally separate the frontend scene contract from backend
provider registration.

```text
website/app scene config
  declares where components mount, which app/runtime serves them,
  which target surfaces they expose, and which object-action gateway to call

backend app config
  declares which apps provide named services, widgets, events, cron jobs,
  ReAct event-source policies, and canvas/provider resolver policies
```

The scene host should not hardcode namespace semantics. It may contain host
composition policy such as "the task editor surface is mounted at this rail" or
"the chat surface accepts attach drops". It must not decide what a `mem:`,
`task:`, `fi:`, or `conv:` object means beyond passing the full object ref to a
configured provider or surface.

## Genericity Status

The current implementation is clean enough for the website scene integration
path: scene mechanics are config-driven, object opens go through a configured
object-action gateway, and canvas pins preserve opaque provider refs. The
remaining non-generic pieces are explicit compatibility/presentation policy or
known follow-up cleanup, not hidden behavior branches in the scene host.

| Area | Current status | Remaining non-generic behavior |
| --- | --- | --- |
| Website scene (`website/index.html`, `website/scene-summon.js`, `website/scene-context-drag.js`) | Config-driven. Components, target surfaces, drop targets, namespace presentation, ready rules, runtime profiles, object-action gateway, and command contracts are read from `kdcube.config.json`. | Drop-target compatibility may use explicit host policy patterns such as `conv:*`, `mem:*`, or `task:*`. This is acceptable composition config for now; provider/surface-declared compatibility is the stronger future target. |
| `@kdcube/components-core/scene` | Generic surface-command and drag/drop runtime. It routes `kdcube.surface.command`, delegates open through an injected `objectAction` client, and accepts drop compatibility from config. | `eventBus.ts` still maps `event.step === "accounting"` to `accounting.usage`. That should become provider/config normalization. |
| `@kdcube/components-core/canvas` | Provider pins are stored as opaque `object_ref`; canvas-owned content uses canvas-owned refs and kinds. Card `kind` is a display label, not a behavior selector. | Some chat/file UI paths still know the durable `fi:` direct-download shape. This should move behind object-action/provider capabilities. Canvas-owned text labels such as `provided.text` and `agent.text` remain local hosted-content labels, not provider-object routing keys. |

## What Belongs In Scene Config

Scene config owns:

- runtime aliases: origin, tenant, project, auth provider;
- component aliases: app id, route, runtime, mount policy, size, rail, target surfaces;
- host-visible surface command contracts;
- context drag/drop policies and effects;
- namespace presentation endpoint;
- object-action gateway endpoint;
- profile selection for local, staging, demo, and mixed-runtime websites.

Scene config does not own:

- per-component event subscription lists;
- provider-specific payload builders;
- object URI parsing rules;
- memory/task/file/conversation behavior;
- ReAct block production policies;
- provider schemas.

Components should claim the events they need after scene configuration is
delivered. Providers should resolve object actions and return target surfaces,
capabilities, and UI events. The scene relays and routes those results.

## Config-Driven Test Checklist

When checking whether a scene remains generic:

1. Search host code for concrete namespace prefixes such as `mem:`, `task:`,
   `conv:`, and `fi:`. Host config may contain explicit compatibility policy
   for a composed website, but host code should not branch on these prefixes.
2. Search host code for app ids such as `versatile@...`, `task-tracker@...`,
   `news@...`, or `kdcube.stats@...`. They should appear in config, not core
   scene logic.
3. Drop an object onto every target surface. The scene should either dispatch
   a generic `kdcube.surface.command` or call the configured object-action
   gateway with the full `object_ref`.
4. Open a provider object from canvas. The canvas should call a resolver/action
   provider and use returned presentation/capabilities, not infer behavior from
   card kind.
5. Run one chat turn and verify event claims: usage card refresh, stats
   snapshot, and task/memory updates should be routed through component claims
   or provider event policies, not host fallback subscriptions.
