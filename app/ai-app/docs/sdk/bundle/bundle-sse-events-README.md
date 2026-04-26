---
id: ks:docs/sdk/bundle/bundle-sse-events-README.md
title: "Bundle SSE Events (Moved)"
summary: "Compatibility page. The shared chat stream event catalog now lives in bundle-chat-stream-events-README.md because the semantic event envelope is shared by SSE and Socket.IO."
tags: ["sdk", "bundle", "sse", "socketio", "events", "moved"]
keywords: ["bundle sse events moved", "chat stream event catalog", "socketio event catalog"]
see_also:
  - ks:docs/sdk/bundle/bundle-chat-stream-events-README.md
  - ks:docs/sdk/bundle/bundle-client-communication-README.md
---
# Bundle SSE Events (Moved)

This page was renamed.

Use:

- [bundle-chat-stream-events-README.md](bundle-chat-stream-events-README.md)

Reason:

- the semantic chat event envelope is shared by both:
  - SSE
  - Socket.IO
- only the transport framing differs

Read together with:

- [bundle-client-communication-README.md](bundle-client-communication-README.md)

That page defines:

- how clients connect
- how clients authenticate
- how clients send chat requests into the stream
- how peer targeting works
