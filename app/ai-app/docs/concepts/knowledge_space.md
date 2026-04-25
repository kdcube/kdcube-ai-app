---
id: knowledge_space
kind: concept
name: Knowledge Space
aliases: ["ks:", knowledge namespace]
category: data
scope: framework
related: [bundle, code_graph]
realized_by:
  - kdcube_ai_app.apps.chat.sdk.retrieval.kb_client.KBClient
  - kdcube_ai_app.apps.knowledge_base.db.data_models.HybridSearchParams
pitfalls:
  - Knowledge spaces are read-only at the agent level — never mutate `ks:` paths during a turn.
  - A bundle's knowledge index lives in `bundle_storage` and is rebuilt when the `knowledge.signature` changes; deleting only the index without bumping the signature leads to a stale state.
---

# Knowledge Space

The **knowledge space** is a bundle-scoped, read-only corpus of reference
material — docs, source files, deployment manifests, and tests — surfaced
to the agent through the `ks:` logical-path prefix. Bundles declare their
knowledge sources in `bundle_props.knowledge` (repo + ref or local roots),
and the entrypoint reconciles them at load time and before each turn.

Retrieval is hybrid: BM25 + ANN over `retrieval_segment` rows, optionally
joined with `datasource` for provider, expiration, publication, and
modification filters. KBClient.hybrid_pipeline_search exposes the full
parameter set (`top_n`, `min_similarity`, `distance_type`, `should_rerank`,
temporal filters, providers).

The knowledge space is one of the framework's four named data spaces; the
others are versioned turn artifacts (`fi:`), the current-turn workspace,
and the conversation sources pool.
