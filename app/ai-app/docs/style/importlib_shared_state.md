---
id: importlib_shared_state
kind: policy
name: Importlib Shared-State Module
aliases: [shared module pattern, importlib pattern]
category: style
scope: framework
related: []
governs: []
rationale: |
  Bundle code is loaded by `importlib.util.spec_from_file_location` with a
  freshly minted module name, which means relative imports do not work
  and a class defined in two different bundles via different loads
  becomes two distinct types. To share runtime state (a connected
  client, a feature flag, a knowledge root) across the bundle's tools
  and the entrypoint, both sides must agree on a *named* module loaded
  through `sys.modules`.
how_to_apply: |
  - Designate a stable module name (e.g. `_kdcube_code_graph_state`).
    Both the entrypoint and the tool modules use the same name when
    they call `_load_state()`.
  - The state module exposes module-level globals (`CLIENT`,
    `SEARCH_ENABLED`, `KNOWLEDGE_ROOT`) and nothing else.
  - The first call loads the module via `importlib.util.find_spec` /
    `spec_from_file_location` and stores it in `sys.modules`; subsequent
    calls return the cached module.
  - Producers (entrypoint) write to the globals at the start of each
    turn. Consumers (tools) read at call time. Never import the
    producer module from the consumer or vice versa.
pitfalls:
  - Using `from .state import CLIENT` — this binds at import time and
    will not see later writes.
  - Letting two modules pick different names for the same shared state.
    They will not share anything; bugs reproduce only under specific
    bundle layouts.
  - Storing per-turn state. The shared module is process-global. Only
    state that is safe to share across turns belongs here.
---

# Importlib Shared-State Module

Bundles are loaded as standalone modules via `importlib.util`, which
breaks the usual import equivalence assumptions. The framework's
solution is a *named* shared-state module accessed via `sys.modules`:
both the entrypoint and the bundle's tool modules import the same
module name through a small loader function, and read/write
process-global state on it.

This is what powers the `CodeGraphClient` shared between
`react.code/entrypoint.py` and `sdk/tools/code_graph_tools.py`, and the
`SEARCH_ENABLED` flag shared between the entrypoint and the bundle's
knowledge resolver.
