---
id: website@2026-07-12/docs/journal/2026-07-13-viewport-bound-scene-height
title: "Viewport-Bound Scene Height"
summary: "Keep the website-owned Scene frame at viewport height while nested surfaces report intrinsic content sizes."
status: active
tags: ["journal", "website", "scene", "iframe", "resize"]
---

# Viewport-Bound Scene Height

## Symptom

The website initially filled the available browser area. After nested surfaces
loaded, the Workspace Scene iframe visibly contracted to a short content height
and left the remaining website viewport empty.

## Cause

Static UI serving installs an intrinsic-content resize reporter by default.
Workspace Scene relays nested surface messages to its parent. A nested
`kdcube-resize` message therefore reached the website reporter, which applied
the nested surface height to the outer Scene iframe.

The website and the embedded Scene use viewport layout. Intrinsic content
height belongs to content-sized widgets and local Scene windows.

## Resolution

- The website index declares `data-kdcube-resize-reporter="opt-out"`.
- `#workspace-scene` keeps stylesheet-owned `height: 100% !important`.
- The package contract test requires both viewport-ownership guards.

Nested widgets continue publishing resize messages for their own local
surfaces, while the website keeps the Scene in the full remaining viewport.
