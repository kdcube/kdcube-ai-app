---
id: factory_pattern
kind: policy
name: Factory Function for Optional Backends
aliases: []
category: style
scope: framework
related: [null_object_pattern]
governs:
  - kdcube_ai_app.apps.chat.sdk.streaming.versatile_streamer.ChannelSubscribers
  - kdcube_ai_app.apps.chat.sdk.retrieval.code_graph_client.CodeGraphClient
rationale: |
  When a class has multiple legitimate variants (real vs null, configured
  vs default) the construction logic does not belong inside __init__.
  Factories centralise the "which variant?" decision, fail fast on bad
  configuration, and let call sites stay free of feature flag checks.
how_to_apply: |
  - Name the factory `create_<thing>` and place it next to the class it
    constructs.
  - Read configuration once; raise a clear error on missing required
    fields. Optional flags fall back to documented defaults.
  - For optional backends: return the null variant when the feature is
    disabled or when the real construction raises a known failure.
  - Do NOT make the factory async. If async init is needed, return the
    constructed instance and let the caller `await client.init()`.
pitfalls:
  - Putting the variant decision in `__init__` itself, leading to
    classes that know about their own absence — the wrong abstraction.
  - Hiding configuration errors behind silent fallbacks. The factory
    should log loudly when it falls back to a null variant.
---

# Factory Function for Optional Backends

A factory function is the right home for the "real or null?", "configured
or default?" decision. It keeps the class itself focused on its core
responsibility and gives callers a single, documented entry point.

In KDcube the convention is `create_<thing>(settings=None) -> Thing |
NullThing`, returning the null variant when the underlying feature is
disabled or unreachable.
