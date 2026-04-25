---
id: code_graph
kind: concept
name: Code Graph
aliases: [code knowledge graph, coding-core graph]
category: data
scope: framework
related: [knowledge_space, bundle]
realized_by:
  - kdcube_ai_app.apps.chat.sdk.retrieval.code_graph_client.CodeGraphClient
  - kdcube_ai_app.apps.chat.sdk.retrieval.code_graph_client.NullCodeGraphClient
pitfalls:
  - When `APP_GRAPH_ENABLED` is false (or Neo4j is unreachable) the factory returns a NullCodeGraphClient. Tools must check `enabled` before issuing queries.
  - Re-indexing the codebase changes qualified_names if modules move; consumers caching qualified_names across runs will get stale references.
---

# Code Graph

The **code graph** is a Neo4j-backed knowledge graph of the codebase
itself: packages, modules, classes, methods, functions, properties,
inheritance, calls, decorators, tests, and documentation links. Bundles
that need structural code understanding (e.g. the `react.code` code
assistant) talk to it via `CodeGraphClient`.

The client exposes high-level traversals — `code_search`, `class_footprint`,
`show_architecture`, `find_references`, `trace_call_chain`,
`find_docs_for_code`, `impact_analysis`, `show_contract`, `find_siblings`,
`find_entry_points` — backed by hybrid retrieval (vector + fulltext) for
search and direct Cypher for structural queries.

The same graph also stores the framework's *semantic layer* (Concept and
StylePolicy nodes) alongside structural nodes, so a single query can
return both *what a class is* and *what it means* in the framework.
