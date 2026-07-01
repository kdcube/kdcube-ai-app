---
id: sdk/solutions/storage
title: "Storage Solution"
summary: "Shared SDK source for the privileged operational storage browser widget."
status: active
tags: ["sdk", "storage", "widget", "admin"]
---

# Storage Solution

The storage browser widget is shared SDK UI source. Apps that expose the
privileged storage browser should point their widget build configuration at:

```text
sdk://solutions/storage/ui.widget.storage
```

`kdcube-services@1-0` is the built-in app that serves this widget as
`bundle_storage`. The widget calls the platform admin storage APIs under
`/api/admin/control-plane/storage` plus the processor registry API at
`/admin/integrations/bundles/storage-registry`.

Cloud deployments must mount the browsed local roots into `chat-ingress`,
because the storage APIs run in ingress.
