---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/scene/surface-layering-README.md
title: "Scene Surface Layering"
summary: "Shared z-index convention for host scenes: a small named tier scale so a surface opened on top of an active full-screen overlay (e.g. an issue wizard opened from inside an expanded chat) always lands in front instead of behind it."
status: active
tags: ["sdk", "solutions", "scene", "layering", "z-index", "overlay", "modal", "ui-convention"]
keywords:
  [
    "z-index convention",
    "surface layering",
    "overlay modal",
    "expanded chat",
    "wizard behind chat",
    "stacking context",
    "scene host layering",
  ]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/scene/scene-event-orchestration-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/scene/scene-composition-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/scene/scene-surface-registry-README.md
---
# Scene Surface Layering

A host scene stacks several surfaces — a chat panel, an expandable side pane, a
canvas, a wizard/editor, transient toasts. Each host historically picked its own
`z-index` magic numbers, which produces a recurring bug:

Event delivery between those surfaces is a separate concern. The layering rules
only decide what appears on top; [Scene Event Orchestration](scene-event-orchestration-README.md)
decides how runtime events are relayed to widgets.

> A surface opened **from within** or **on top of** a full-screen overlay renders
> **behind** that overlay.

Concrete case: the chat is expanded to a full overlay; the user clicks a task
object inside it; the issue **wizard opens behind the expanded chat**.

The cause is always the same — the overlay sits at a high `z-index`, and the
newly-opened surface lands in its in-flow slot at a lower one. The fix is a
shared **tier scale** plus one rule.

## The rule

> A surface opened on top of the active full-screen overlay uses the
> **`overlay-modal`** tier, which is above the **`overlay`** tier.

## The tier scale

Define these as CSS custom properties in the host's `:root` and reference them
everywhere instead of bare numbers:

```css
:root {
  --z-content:        1;   /* normal in-board content, placed cards */
  --z-raised:        10;   /* hover-raised cards, in-content popovers */
  --z-rail:          20;   /* docked side rails / sticky toolbars */
  --z-overlay:       90;   /* a surface expanded to a full-screen overlay (chat, a pane) */
  --z-overlay-rail: 100;   /* controls pinned to the active overlay (its rail buttons) */
  --z-overlay-modal:120;   /* a surface/modal opened ON TOP of the active overlay */
  --z-toast:        200;   /* transient notices/toasts — always on top */
}
```

Gaps between tiers are intentional: a host can place its own sub-levels inside a
tier (e.g. two stacked in-content popovers at `--z-raised` and `--z-raised + 1`)
without colliding with the next tier.

## Applying it

- The expanded surface (chat, an expanded pane) → `--z-overlay`.
- Controls attached to that overlay (rail/close buttons) → `--z-overlay-rail`.
- **Anything opened on top of it** (a wizard/editor, a confirm dialog reached
  from inside the overlay) → `--z-overlay-modal`, plus `pointer-events: auto`
  if the surface behind it was made inert.
- Toasts/notices → `--z-toast`.

### Stacking-context caveat

`z-index` only competes **within the same stacking context**. A high
`--z-overlay-modal` on a deeply-nested element does nothing if an ancestor
created a stacking context with a lower `z-index`. Two safe patterns:

- Give the modal surface `position: fixed` (or `absolute` relative to the scene
  root) and ensure no ancestor between it and the overlay creates a stacking
  context (no `transform` / `opacity < 1` / `filter` / positioned `z-index`).
- Or hoist the modal to the scene root (portal) before applying the tier.

## Raise on activation

Within the floating-window band, hosts apply standard window-manager focus
semantics: pointer-down anywhere on a window — titlebar OR content — raises it
above the other floating windows (a monotonic z-counter inside the band; the
rail, toasts, and drag overlays stay above, docked stage content stays below).

Two mechanisms are required, because iframe surfaces split the input paths —
and the raise must stay deterministic when the scene is ITSELF an iframe of an
outer host, where the scene window may never hold focus (so focus/blur
observation on the scene window is the wrong foundation):

1. **Chrome clicks** — a capture-phase pointerdown handler on the window
   container raises it. This covers the titlebar, grip, and any host chrome.
2. **Clicks aimed at a buried window's content** — a transparent **raise
   veil**: a parent-owned click catcher covering the body of every floating
   window that is not on top. Because the veil lives in the scene document,
   the pointer-down always reaches the scene regardless of nesting; the veil
   raises the window and unmounts as it becomes top, so the follow-up
   pointerup/click falls through to the iframe. The topmost window carries no
   veil and interacts directly.

As a complement, the host arms a `focus` listener on each frame's
`contentWindow` on every iframe load (same-origin scene widgets; try/catch for
opaque frames): focus entering a frame by any path — keyboard, programmatic —
also raises its window.

Raises also fire on drag-start, on unpin/promotion, and on a rail tap on a
buried open window (only a tap on the topmost window closes or docks it).
The workspace scene host (`ui/scene/src/windows.tsx` + `main.tsx`) is the
reference implementation of this contract; its raise decisions log under the
`[kdc-scene:focus]` console prefix.

## Reference implementation

The task-tracker host app applies this scale: the expanded chat is `--z-overlay`,
its rail buttons `--z-overlay-rail`, and the issue wizard opened from inside the
expanded chat is floated at `--z-overlay-modal` (a centered modal, with the chat
dimmed behind). See its `ui/main/src/styles.css`.

The workspace scene host keeps one z-band for floating windows (raised
monotonically as described above) below its rail/notice/drag-overlay tiers;
hosts adopting the tier tokens should map that band inside `--z-overlay`.
