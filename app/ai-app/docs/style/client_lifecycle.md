---
id: client_lifecycle
kind: policy
name: Async Client Lifecycle
aliases: [init/close pattern]
category: style
scope: framework
related: [null_object_pattern]
governs:
  - kdcube_ai_app.apps.chat.sdk.retrieval.kb_client.KBClient
  - kdcube_ai_app.apps.chat.sdk.retrieval.code_graph_client.CodeGraphClient
  - kdcube_ai_app.apps.chat.sdk.context.vector.conv_index.ConvIndex
rationale: |
  Async clients (asyncpg pool, Neo4j driver, sentence-transformers wrapper)
  cannot do real work in `__init__` because there is no running event
  loop and no way to surface failure cleanly. Splitting construction from
  `init()` and pairing it with `close()` keeps lifecycle explicit and
  makes the "is this client warm?" question observable.
how_to_apply: |
  - `__init__` accepts dependencies (pool, settings, logger) and stores
    them. It must not perform I/O or connect to anything.
  - `async def init(self)` performs all I/O — pool creation, schema
    bootstrap, model load, connection check. Idempotent: a second call
    is a no-op.
  - `async def close(self)` releases resources. Skip closing pools that
    were passed in (`self.shared_pool`); only close what you created.
  - Bundle entrypoints orchestrate this: construct → `await init()` →
    use → `await close()` in a finally block.
pitfalls:
  - Calling `init()` from a synchronous constructor by `asyncio.run` —
    this breaks when the bundle itself is already inside an event loop.
  - Closing a shared pool because the client owns the close call. Track
    `shared_pool` and skip close when True.
---

# Async Client Lifecycle

KDcube's async retrieval and storage clients follow a strict three-phase
lifecycle: construct, `await init()`, `await close()`. Construction is
synchronous and side-effect free; all I/O happens in `init()`; `close()`
releases what `init()` allocated.

This is the pattern that lets bundle entrypoints orchestrate clients
inside a LangGraph node without leaking pools or driver connections, and
without surprising the caller with deferred construction-time errors.
