# Coding-Core Semantic Layer — Design

> Status: design (v0.1). No implementation yet. Lives inside the portable
> `coding-core/` folder so it travels with the indexer to any project.

## Goal

Extend the code knowledge graph beyond *structural* facts (classes, methods,
calls, docs) with a *semantic* layer that captures:

1. **Framework concepts** — first-class entities a developer reasons about
   (Bundle, Skill, Channel, Timeline, Plan, Sources Pool, …).
2. **Code style policies** — recurring conventions and the *why* behind them
   (client lifecycle, factory pattern, importlib shared state, …).
3. **Glossary terms** — vocabulary items that need a definition but aren't
   full architectural concepts (turn, thread_id, comm_context, …).

Result: when the LLM reaches the graph via MCP, it gets *meaning* alongside
*shape*, and can reproduce the framework's idioms when generating new code.

The whole layer is **portable**. The schema, ingestion logic, and MCP tools
live in `coding-core/`. The actual content (concept/policy `.md` files) lives
in the project being indexed.

---

## Decisions taken

| Decision | Choice | Rationale |
|---|---|---|
| Node modeling | One label `Semantic` with a `kind` tag | Simpler graph; mixed retrieval; avoids combinatorial constraint/index growth |
| Body length | Always extended (no summary truncation) | Tools must be able to ground LLM in the *full* explanation |
| Aliases | Stored as a list property | No deprecated-alias tracking needed for v1 |
| Authoring source | Markdown + YAML frontmatter, version-controlled with the project | Devs read/edit it as they would docs; piggybacks on existing DocSection pipeline |
| Pattern mining | LLM-assisted, opt-in, on-demand | Costs tokens; should not run on every reindex |
| Per-bundle vocab | Bundle ships its own `concepts/` dir; nodes namespaced by `scope` | Bundles can extend vocabulary without touching framework docs |

---

## Graph schema (additive, alongside existing structural nodes)

### Node label `Semantic`

```cypher
CREATE CONSTRAINT semantic_id IF NOT EXISTS
  FOR (s:Semantic) REQUIRE (s.scope, s.id) IS UNIQUE;
```

| Property | Type | Notes |
|---|---|---|
| `id` | string | Slug, unique per scope, e.g. `bundle`, `factory-pattern`. |
| `kind` | string | `concept` \| `policy` \| `term`. |
| `name` | string | Display name. |
| `aliases` | list[string] | Synonyms / common misnomers (e.g. `["plugin"]`). |
| `category` | string | Free-form tag — `architectural` \| `runtime` \| `data` \| `lifecycle` \| `streaming` \| `style` \| `governance`. |
| `summary` | string | 1–2 sentences. Used in graph hover and truncated views. |
| `definition` | string | Full long-form. Used by LLM for grounding. |
| `rationale` | string | Mostly for `policy` — the *why*. |
| `how_to_apply` | string | Mostly for `policy` — when/where it kicks in. |
| `pitfalls` | list[string] | Common mistakes. |
| `examples` | list[string] | qualified_names of code that exemplifies the entry. |
| `scope` | string | `framework` or a specific `<bundle_id>`. |
| `source` | string | `authored` \| `auto-mined`. |
| `source_path` | string | File path of the source markdown. |
| `revision` | int | Bumped on each re-ingest. |
| `embedding` | vector[dim] | For semantic search. |

### Indexes

```cypher
CREATE INDEX semantic_name      IF NOT EXISTS FOR (s:Semantic) ON (s.name);
CREATE INDEX semantic_kind      IF NOT EXISTS FOR (s:Semantic) ON (s.kind);
CREATE INDEX semantic_category  IF NOT EXISTS FOR (s:Semantic) ON (s.category);
CREATE INDEX semantic_scope     IF NOT EXISTS FOR (s:Semantic) ON (s.scope);

CREATE FULLTEXT INDEX semantic_text IF NOT EXISTS
  FOR (s:Semantic) ON EACH [s.name, s.aliases, s.summary, s.definition];

CREATE VECTOR INDEX semantic_embedding IF NOT EXISTS
  FOR (s:Semantic) ON (s.embedding)
  OPTIONS {indexConfig: {`vector.dimensions`: $dims, `vector.similarity_function`: 'cosine'}};
```

### Edges

| Edge | From → To | Meaning |
|---|---|---|
| `EMBODIES` | Class \| Method \| Module \| Package → Semantic{kind:'concept'} | Symbol is an instance of the concept. |
| `EMBODIED_BY` | Semantic → Class \| Method \| … | Inverse, for fast "show me all bundles". |
| `GOVERNED_BY` | Class \| Method \| Module → Semantic{kind:'policy'} | This style policy applies here. |
| `RELATED_TO` | Semantic → Semantic | Concept-to-concept graph (Bundle ↔ Skill ↔ Tool). |
| `DEFINED_IN` | Semantic → DocSection | Provenance to the existing DocSection ingestion. |

---

## Authoring source

### A. Markdown with YAML frontmatter (canonical)

Layout — these are paths *inside the project being indexed*, not inside
`coding-core/`:

```
<project>/docs/concepts/<id>.md       # framework-wide concepts
<project>/docs/style/<id>.md          # style policies
<bundle>/concepts/<id>.md             # bundle-scoped concepts
```

Example file shape:

```markdown
---
id: bundle
kind: concept
name: Bundle
aliases: [plugin]
category: architectural
scope: framework
related: [skill, tool, knowledge_space]
realized_by:
  - kdcube_ai_app.infra.plugin.bundle_registry.BundleSpec
  - kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint.BaseEntrypoint
pitfalls:
  - Bundle path must be importable; symlinks under git submodules can break loading.
  - Bundles ship their own knowledge space — don't share roots across bundles.
---

# Bundle

Full long-form definition goes here. Always extended; never truncated.

## Lifecycle
…

## Anatomy
…
```

Indexer:

1. Globs configured roots (`semantic.concept_roots`, `semantic.bundle_concept_glob`).
2. Parses frontmatter; rejects files missing `id`, `kind`, `name`.
3. Writes `Semantic` node (frontmatter → properties; body → `definition`).
4. Resolves `realized_by` qualified_names → `EMBODIES`/`EMBODIED_BY` edges.
   Unresolved entries logged as warnings.
5. Resolves `related` → `RELATED_TO` edges.
6. Body chunked + ingested as `DocSection` (existing pipeline) and linked
   via `DEFINED_IN` for inline citation.

### B. LLM-assisted pattern mining (opt-in)

Goal: capture *recurring code patterns* the human author hasn't explicitly
documented, so the LLM can later reproduce them faithfully.

Two-phase pipeline, run on demand via the `mine_patterns` MCP tool or a
post-index hook (configurable):

**Phase 1 — sample-and-summarize**
- For each module above a size threshold, the indexer collects top-N
  representative classes/methods (ranked by call-graph centrality + length).
- The selected source is sent to a configurable LLM endpoint with a
  structured prompt: *"Identify recurring style policies — lifecycle, error
  handling, import order, async pattern, factory usage, null-object usage, …
  For each, return: title, rule, rationale (the WHY), how_to_apply,
  examples (qualified_names from the input)."*
- Output validated against a Pydantic model; rejected entries logged.
- Each accepted policy → `Semantic{kind:'policy', source:'auto-mined'}`
  node + `GOVERNED_BY` edges to the example symbols.

**Phase 2 — propagate**
- For each mined policy, embedding similarity to its example symbols is used
  to find further symbols that likely match.
- Additional `GOVERNED_BY` edges added with a `confidence` property on the
  edge (cutoff configurable).

**Merge rules** when both authored and mined entries exist for the same `id`:

- `definition`, `rationale`, `how_to_apply` — authored wins.
- `examples`, `pitfalls` — union (mined extends authored).
- `source` field becomes `authored+mined`.

---

## How the LLM consumes it

Three changes to the existing tool surface plus one new tool. No new schema
on the LLM-facing side beyond extra fields in existing JSON returns.

### 1. `class_footprint` — augmented return

JSON gains two top-level fields:

```json
{
  "class": { … existing … },
  "ancestors": [ … ],
  "methods": [ … ],
  "concepts":       [ {"id":"bundle", "name":"Bundle", "summary":"…"} ],
  "style_policies": [ {"id":"factory-pattern", "title":"…", "summary":"…"} ]
}
```

The LLM picking up a class footprint now sees both *what it is* (concepts)
and *how it should be written* (style policies), not just *what it has*.

### 2. `code_search` — Semantic nodes as first-class results

`Semantic` nodes are searched alongside `Class`/`Method`/`Function`. Result
entries gain a `kind` field (`class` | `method` | … | `concept` | `policy`).
Aliases boost match score for fulltext queries. Useful for: *"what is a
channel?"* → top hit is the `channel` Concept.

### 3. `define` — direct lookup (new MCP tool)

```python
define(term: str, scope: str = "framework") -> dict
```

- Looks up `Semantic` by `name` or any `aliases[*]`, optionally narrowed by
  `scope` (defaulting to `framework`, falling back to bundle scopes).
- Returns the full record + `RELATED_TO` neighbors + `EMBODIED_BY` symbols.
- Cheap, unambiguous; useful when the LLM (or a future "?" UI button) wants
  the canonical definition without surrounding code.

### Deferred to v2

- `find_by_concept(concept_id)` — return all `EMBODIED_BY` symbols. Trivial
  to add; deferred only because `class_footprint` covers most use cases.
- `mine_patterns` continuous mode (run mining over diffs only).

---

## What goes in `coding-core/`

This is the portable surface. Anything kdcube-specific stays in the
*project's* doc tree, not here.

| File | Responsibility |
|---|---|
| `extraction/semantic_extractor.py` | Parses `*.md` with frontmatter into `Semantic` records; resolves `realized_by` and `related`. |
| `extraction/pattern_miner.py` | LLM-assisted mining; talks to a configurable LLM endpoint. |
| `graph/schema.py` | Extended with `Semantic` constraints, indexes, fulltext, vector. |
| `graph/writers.py` | `write_semantic_nodes`, `write_semantic_edges`, merge logic. |
| `graph/queries.py` | Cypher for footprint+concepts, code_search w/ Semantic, define. |
| `server.py` | New MCP tools (`define`, `mine_patterns`); existing `class_footprint` and `code_search` augmented. |
| `config.json` | New `semantic` section (see below). |
| `README.md` | New "Semantic Layer" section pointing here. |
| `docs/SEMANTIC_LAYER.md` | This document. |

### `config.json` extension

```json
{
  "semantic": {
    "concept_roots": ["docs/concepts", "docs/style"],
    "bundle_concept_glob": "**/bundles/*/concepts",
    "auto_mine": false,
    "auto_mine_on_index": false,
    "miner": {
      "llm_endpoint": null,
      "model": "gpt-4o-mini",
      "max_samples_per_module": 5,
      "min_module_size_loc": 200,
      "confidence_cutoff": 0.65
    }
  }
}
```

---

## Seed inventory (lives in the kdcube project, not here)

These get authored as `<kdcube>/app/ai-app/docs/concepts/*.md` and
`<kdcube>/app/ai-app/docs/style/*.md`. Drawn from the ReAct v2 doc and
existing codebase patterns.

### Concepts — architectural & packaging
- `bundle`, `skill`, `tool`, `kernel_function`, `plugin`,
  `knowledge_space`, `service_hub`

### Concepts — runtime / loop
- `react_loop`, `turn`, `gate_agent`, `single_agent_loop`,
  `contribute_block`, `announce_block`, `plan`, `plan_ack`,
  `block`, `artifact`

### Concepts — memory & context
- `timeline`, `three_checkpoint_caching`, `compaction`, `ttl_expiry`,
  `sources_pool`, `sid` (source id), `citation_replacement`

### Concepts — streaming & channels
- `channeled_streamer`, `thinking_channel`, `answer_channel`,
  `followup_channel`, `canvas_channel`, `usage_channel`,
  `structured_decision_channel`, `composite_json_streamer`,
  `channel_subscriber`

### Concepts — data spaces & addressing
- `logical_path`, `namespace_prefix`, `ks_prefix` (`ks:`),
  `fi_prefix` (`fi:`), `ar_prefix` (`ar:`), `so_prefix` (`so:`),
  `su_prefix` (`su:`), `tc_prefix` (`tc:`),
  `current_turn_workspace`, `workspace_scope`, `turn_log`

### Concepts — react.* in-loop tools
- `react_read`, `react_write`, `react_pull`, `react_patch`,
  `react_checkout`, `react_memsearch`, `react_hide`,
  `react_search_files`, `react_search_knowledge`

### Concepts — governance
- `governance_attachment_points`, `evidence_over_inference`

### Style policies (drawn from existing codebase patterns memory)
- `client_lifecycle`, `factory_pattern`, `null_object_pattern`,
  `importlib_shared_state`, `config_resolution`, `event_filter`,
  `neo4j_async`, `import_ordering`, `docker_naming`,
  `parameter_ordering_contract`, `contribute_then_observe`,
  `render_decision_contribute`, `logical_path_materialization`,
  `hidden_content_placeholder`, `citation_token_handling`,
  `namespace_validation`

Total: ~40 concept docs + ~16 policy docs for v1 seed.

---

## Migration & rollout

1. Land schema additions in `graph/schema.py`. Idempotent — safe on existing
   graphs.
2. Land `semantic_extractor.py` + `writers.py`. New CLI: `index_semantics`.
3. Land MCP tool changes in `server.py`. Deploy.
4. Author seed `concept` and `policy` markdown in the project.
5. Run `index_semantics`. Verify graph counts.
6. Optional: enable `auto_mine` and run `mine_patterns` once to bootstrap.

Each step is independently revertable; nothing in the existing structural
graph is mutated by Semantic ingestion.

---

## Open decisions for the user

1. **Folder location of this design doc** — currently
   `integration/coding-core/docs/SEMANTIC_LAYER.md`. If you want a different
   layout (e.g. literally a `code-core/` folder at repo root), say where.
2. **LLM endpoint for mining** — should the miner default to the same LLM
   the chat backend uses, or be configured separately?
3. **Confidence cutoff for `GOVERNED_BY` edges via mining** — default 0.65
   (≈ a moderately strict embedding similarity). Tighter / looser?
4. **Bundle-scoped vocab visibility** — when a question is asked outside a
   bundle context, do we include bundle-scoped concepts in `define` /
   `code_search` results, or hide them unless the bundle is "active"?
5. **Per-bundle UI in Bundle Builder** — should the Bundle Builder show a
   "Concepts in this bundle" panel (sourced from this layer) for the
   developer's own bundle?
