---
id: ks:docs/sdk/bundle/bundle-client-ui-README.md
title: "Bundle Client UI"
summary: "Entry page for bundle-facing frontend integration: which client docs to read for browser transport, auth, chat stream lifecycle, multi-tab behavior, and widget or operation interoperability."
tags: ["sdk", "bundle", "frontend", "transport", "auth", "sse", "socketio", "rest", "ui"]
keywords: ["frontend integration entrypoint", "bundle ui contract", "widget and operation interoperability", "browser auth and transport", "chat stream lifecycle guidance", "multi tab coordination", "client side bundle behavior"]
see_also:
  - ks:docs/sdk/bundle/bundle-client-communication-README.md
  - ks:docs/sdk/bundle/bundle-chat-stream-events-README.md
  - ks:docs/sdk/bundle/bundle-frontend-awareness-README.md
  - ks:docs/sdk/bundle/bundle-interfaces-README.md
  - ks:docs/service/auth/auth-README.md
  - ks:docs/service/comm/README-comm.md
---
# Bundle Client UI

This section is the browser/UI entry point for bundle developers.

Use it when your bundle ships:

- widgets
- a custom iframe main view
- a custom frontend calling `/api/integrations/*`
- frontend code that must consume chat stream events correctly

## Read Order

1. [bundle-client-communication-README.md](bundle-client-communication-README.md)
   The transport/auth contract: supported headers, cookies, query params, response headers, SSE vs Socket.IO, and how REST requests can target one connected peer.
2. [bundle-chat-stream-events-README.md](bundle-chat-stream-events-README.md)
   The shared SSE + Socket.IO chat stream event catalog and envelope shape.
3. [bundle-frontend-awareness-README.md](bundle-frontend-awareness-README.md)
   Retry, draining, rate-limit, reconnect, and multi-tab behavior.

## Scope

Use these docs when you need to know:

- how bundle UIs authenticate over REST, SSE, Socket.IO, and integrations
- which cookies and headers are supported
- which values are configurable by env
- how `stream_id` and `KDC-Stream-ID` affect peer-targeted delivery
- which response headers and retry signals the client should honor

This is no longer a separate top-level client namespace. These docs live under bundle because bundle code now owns widgets, iframe UIs, and custom frontend interactions.

## Server-Side References

- auth transport and precedence:
  [auth-README.md](../../service/auth/auth-README.md)
- transport and relay internals:
  [README-comm.md](../../service/comm/README-comm.md)
