---
id: null_object_pattern
kind: policy
name: Null Object Pattern
aliases: []
category: style
scope: framework
related: [client_lifecycle]
governs:
  - kdcube_ai_app.apps.chat.sdk.retrieval.code_graph_client.NullCodeGraphClient
  - kdcube_ai_app.apps.chat.sdk.retrieval.code_graph_client.CodeGraphClient
rationale: |
  Optional infrastructure (Neo4j, external embedding services, alternative
  retrieval backends) must never make a bundle crash on init. Returning a
  Null variant lets the same call sites work whether the dependency is up
  or down, and pushes the "is this enabled?" check into one well-known
  property instead of scattering try/except blocks across tools.
how_to_apply: |
  - Provide a `NullX` class with the same public interface as the real
    client. All methods return safe empty results (empty list, empty
    dict, or a documented "unavailable" sentinel string).
  - Expose an `enabled: bool` attribute. The real client sets it to True;
    the null variant sets it to False.
  - Construct via a factory (`create_X(...)`) that returns the null
    variant when configuration disables the feature or when the real
    client's `__init__` raises.
  - Tools must check `client.enabled` before issuing queries. They must
    not catch exceptions to detect availability.
pitfalls:
  - Forgetting to mirror a method on the null variant — the next agent
    call discovers it as `AttributeError` at the worst possible moment.
  - Letting the real client's failure path swallow exceptions silently
    instead of swapping to the null variant; you lose observability.
---

# Null Object Pattern

When an optional backend (Neo4j, an embedding model, an MCP server) might
not be present at runtime, expose a parallel `NullX` class with the same
public surface. The factory chooses which to return; downstream code
checks `client.enabled` and gets safe empty results when disabled.

This keeps tools and orchestrators simple: there is no conditional client
construction, no try/except around every query, and no "is this enabled?"
check inside the call site.
