---
id: website@2026-07-12/docs/journal/2026-07-13-versioned-site-catalog-and-cdn
title: "Versioned Site Catalog And CDN Routing"
summary: "Moved site selection off descriptor/Redis request reads and added clean multipage CDN routing."
status: active
---

# Versioned Site Catalog And CDN Routing

Application site declarations now follow a projection/hot-serving model:

```text
bundles.yaml
  -> validated catalog
  -> atomic Redis generation + snapshot + event
  -> immutable catalog in every proc
  -> request-time host/alias lookup
```

Catalog publication uses one Redis script so generation assignment, snapshot
replacement, and notification cannot be reordered. Subscribers load the
current snapshot after subscribing and reject delayed generations. Site
requests perform no Redis lookup or descriptor scan for routing.

Site HTML receives a server-injected application context and a clean public
base. Alias routes serve files, directory indexes, and SPA fallbacks. A site
CDN can preserve the viewer host and rewrite `/<path>` to
`/api/integrations/site-root/<path>` without owning a site registry or requiring
application-specific OpenResty configuration.
