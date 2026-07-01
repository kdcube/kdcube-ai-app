---
id: kdcube.admin
title: "KDCube Admin App"
summary: "Built-in privileged fallback app for control-plane access."
status: "mvp"
tags: ["admin", "app", "control-plane"]
see_also:
  - "interface/README.md"
  - "interface/admin-storage.openapi.yaml"
  - "ks:docs/sdk/bundle/bundle-widget-integration-README.md"
  - "ks:apps/chat/sdk/examples/bundles/kdcube-services@1-0/README.md"
---
# KDCube Admin App

`kdcube.admin` is the built-in privileged fallback app used when no default AI
app is configured. It is registered by the platform and is available to users
with privileged access.

## Widgets

`kdcube.admin` does not serve product widgets. The privileged storage browser is
served by `kdcube-services@1-0` as widget `bundle_storage` and built from the
shared SDK source:

```text
sdk://solutions/storage/ui.widget.storage
```

## Runtime Contract

The storage browser uses two backend surfaces:

- Ingress storage APIs under `/api/admin/control-plane/storage`.
- Processor registry API at `/admin/integrations/bundles/storage-registry`.

Local filesystem roots that the widget browses must be mounted into the ingress
runtime, because the storage APIs are served there. The processor runtime also
uses the same roots for bundle execution/build work.

The OpenAPI contract is maintained in
[interface/admin-storage.openapi.yaml](interface/admin-storage.openapi.yaml).
