---
id: kdcube.admin/interface
title: "KDCube Admin Storage API Interface"
summary: "Privileged storage control-plane API contract used by the storage browser widget."
status: "mvp"
tags: ["interface", "openapi", "admin", "storage", "app"]
see_also:
  - "admin-storage.openapi.yaml"
  - "../README.md"
  - "ks:docs/sdk/bundle/bundle-widget-integration-README.md"
---
# KDCube Admin Storage API Interface

The OpenAPI contract is documented in:

- [admin-storage.openapi.yaml](admin-storage.openapi.yaml)

Protected API surfaces:

- `GET /api/admin/control-plane/storage/roots`
- `GET /api/admin/control-plane/storage/tenants-projects`
- `GET /api/admin/control-plane/storage/list`
- `POST /api/admin/control-plane/storage/export`
- `POST /api/admin/control-plane/storage/delete`
- `GET /admin/integrations/bundles/storage-registry`

The storage APIs support scoped browsing, export, and deletion for local
filesystem-backed storage roots. The registry API returns the active app
registry and the managed app folders referenced by that registry, so the storage
browser can highlight active and orphaned managed folders.

The `bundle_storage` widget that consumes these APIs is served by
`kdcube-services@1-0` and built from `sdk://solutions/storage/ui.widget.storage`.

All surfaces are privileged control-plane surfaces and use the platform admin
session.
