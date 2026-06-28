---
id: user-memories@2026-06-26/agents
title: "User Memories — Builder-Agent Onboarding"
summary: "How to work on the memory-only app: derives the SDK memories+economics mixin, enables the memories widget + `mem` named service, ships no UI of its own."
status: active
tags: ["agents", "builder", "onboarding", "memory", "named-service", "widget"]
see_also:
  - "README.md"
  - "interface/README.md"
  - "docs/README.md"
---

# User Memories — Builder-Agent Onboarding

## Read first

- `README.md` — what this app is and why (one memory surface, embedded everywhere).
- `interface/README.md` — operations, widget, `mem` named service, storages, dataflows.
- `entrypoint.py` — the whole behavior (≈1 class).
- SDK mixin: `kdcube_ai_app/apps/chat/sdk/solutions/chatbot/entrypoint_with_memory.py`
  (`BaseEntrypointWithEconomicsAndMemory`, `MemoryEntrypointMixin.memory_configuration_defaults`).
- SDK widget source: `kdcube_ai_app/apps/chat/sdk/context/memory/ui/widget/memories`.

## What this app is

A thin app whose only job is to expose memories once: the SDK memories widget +
the `mem` named service. Other apps embed the widget by iframe and consume `mem`
as a named service instead of republishing the memory module.

## Implementation rules

- **Derive the mixin; don't reimplement memory.** All memory operations, the
  `mem` provider, reconciliation, and snapshots come from
  `BaseEntrypointWithEconomicsAndMemory`. This app only sets `memory.enabled`,
  the widget toggle, and the scope in `configuration_defaults()`.
- **No `ui/` folder.** The widget is built from `sdk://context/memory/ui/widget/memories`.
  Do not copy the widget into this app — that defeats the single-source goal.
- **Scope = the user, not the app.** Memories are user-scoped; keep
  `memory.widget.default_scope_filter: all_user_memories` so this dedicated
  surface shows the user's whole memory set.
- **No chat product.** The graph is a deliberate no-op. Don't add agents/tools
  here — if memory needs to feed an agent, that belongs in the consuming app.
- **Economics is automatic.** Writes/reconciliation are guarded by the economics
  half of the mixin; don't add a second guard.
- **Package-relative imports only** if you ever add modules (none today).

## Validate before release

```bash
python -m py_compile entrypoint.py
PYTHONPATH=<kdcube-source-root> python -m kdcube_ai_app.apps.chat.sdk.tests.bundle.run_bundle_suite \
  --bundle-path <this-folder>
# then a real reload:
kdcube bundle reload
```

Open `…/user-memories@2026-06-26/widgets/memories` and confirm the memories
widget renders, lists the signed-in user's memories, and write actions work.

> Terminology note (rebrand): we say **app**; the platform code still says
> "bundle" (`bundle_id`, `bundles.yaml`, `@bundle_entrypoint`). Same thing.
