---
id: repo:kdcube-ai-app/app/ai-app/docs/recipes/resource_sharing/README.md
title: "Resource Sharing Recipes"
summary: "Short recipes for exposing an app's hosted content — rendered pages, stored files, and built UI — at public, anonymously openable URLs."
status: active
tags: ["recipes", "resource-sharing", "static", "public", "bundle", "storage", "widget"]
updated_at: 2026-06-29
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/recipes/resource_sharing/share-static-resources-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/bundle/bundle-interfaces-README.md
---
# Resource Sharing Recipes

These recipes are practical entry points for making an app's content reachable
at a public URL. They are intentionally shorter and more task-oriented than the
SDK architecture docs.

## Recipes

| Recipe | Use when |
| --- | --- |
| [Share Static Resources](share-static-resources-README.md) | You want to hand someone a plain URL that opens an app-hosted page or file with no sign-in — a rendered page (HTML/PDF), a stored artifact (FS/S3), or, by pointer, a whole built UI. |

## Canonical SDK Docs

For deeper design and implementation contracts, read:

- [Bundle Interfaces](../../sdk/bundle/bundle-interfaces-README.md) — the full set of app surfaces and access levels.
- [Bundle Widget Integration](../../sdk/bundle/bundle-widget-integration-README.md) — the widget UI contract.
- [UI Components Lifecycle](../../sdk/bundle/ui-components-lifecycle-README.md) — how the platform builds, serves, and reloads widget/main-view static.
