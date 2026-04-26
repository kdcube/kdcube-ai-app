# Configuration Assistant — UI Design (final v1)

> A chat-centric, in-product assistant that helps **bundle developers** build
> their own kdcube apps (e.g. "a company app for documents and policies").
> Powered by the code-core MCP graph and the framework's semantic layer.
> Lives alongside the existing chat UI as a separate page.

## Naming

| Surface | Name | Notes |
|---|---|---|
| User-facing page | **Configuration Assistant** | What the developer sees in the URL bar / nav. |
| Underlying engine | **code-core** | The Neo4j graph + MCP tools. Internal only. |
| Bundle that powers it | `react.code` (reused, with `mode=config_assistant` runtime hint) | Already wires `CodeGraphClient`, `KBClient`, knowledge resolver. New bundle = unnecessary duplication for v1. |

## Route + surfacing

- **Direct route**: `/chatbot/config-assistant/:conversationId?` — sibling to `/chatbot/chat`, registered in `AppRouter.tsx` after the existing chat route.
- **Discovery from generic chat**: a `?` icon in `ChatHeader` opens the Configuration Assistant in a new tab (preserves the user's running chat).
- **Top nav entry**: deferred to v1.1 — direct URL is enough to ship.

## Persona + top tasks

Persona: **bundle developer** building their own kdcube app.

v1 flagship task: *"Help me create my company app for documents and company policies usage."* The assistant walks the developer through:
1. Choosing a starter pattern (e.g. doc-RAG bundle).
2. Scaffolding the bundle structure (entrypoint, tools, skills, knowledge space).
3. Wiring KB ingestion + retrieval correctly.
4. Following framework conventions (the style policies — async client lifecycle, factory pattern, importlib shared state, null object pattern).
5. Citing concrete code examples from existing bundles (`react.doc`, `react.code`).

## Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Header: "Configuration Assistant"  ·  tenant/project  ·  + New  ·  ?       │
├──────────┬──────────────────────────────────┬─────────────────────────────┤
│          │                                  │  Inspect panel              │
│  Convs   │     Chat log                     │  ┌──────────────────────┐   │
│  (this   │                                  │  │ [Graph] [Concept]    │   │
│   page   │                                  │  │ [Footprint] [Source] │   │
│   only)  │                                  │  │ [Config] [My Bundle] │   │
│          │                                  │  └──────────────────────┘   │
│  ─────   │                                  │                             │
│  Scope   │                                  │  ●─────●                    │
│  picker  │                                  │  │     │                    │
│  (pkg    │                                  │  ●─────●                    │
│   prefix │                                  │     │                       │
│   filter)│                                  │     ●                       │
│          │                                  │                             │
│          ├──────────────────────────────────┤  ── Selection details ──    │
│          │  [chip] [chip] [chip] [chip]     │  · qualified_name           │
│          │  Composer ─────────────────────  │  · concepts (badged)        │
│          │                                  │  · style policies           │
│          │                                  │  · methods · callers        │
│          │                                  │  · linked docs · tests      │
└──────────┴──────────────────────────────────┴─────────────────────────────┘
```

### Reused primitives

- `ChatLog`, `UserInput` — verbatim from the existing chat.
- Conversation-list portion of `ChatSidePanel` — extracted to a small reusable component for both pages.
- SSE pipeline: `chatServiceMiddleware`, `sseChat` — already supports per-page payload via `payload?: Record<string, unknown>` (added during search-settings work).
- Citations: `sdk/tools/citations.py` token format `[[S:n]]` already supported by the renderer.

### New components (to be implemented)

- `ConfigAssistantPage.tsx` — the route component, top-level layout.
- `ConfigAssistantHeader.tsx` — fixed bundle (`react.code`), no bundle dropdown, "New conversation" + "?" help button.
- `ScopePicker.tsx` — package-prefix dropdown that maps to `package_filter` for `show_architecture`-style queries; persists in `configAssistantUiSlice`.
- `QuickActionChips.tsx` — chip row above composer, content described below.
- `InspectPanel.tsx` — tab bar + lazy-loaded tab content.
- `GraphTab.tsx`, `ConceptTab.tsx`, `FootprintTab.tsx`, `SourceTab.tsx`, `ConfigTab.tsx`, `MyBundleTab.tsx` — one component per tab.

## Quick action chips (above composer)

Behavior: **tap → fill composer with editable text** (focus + cursor at end). User then presses Enter to send. Two-tap flow chosen because devs often want to edit the prompt before sending — single-tap-send is too aggressive.

Chip set on a fresh conversation:
- "Scaffold a doc-RAG bundle for my company"
- "What's a Bundle in kdcube?"
- "Show me bundle anatomy"
- "How do I add a tool to my bundle?"
- "How do I ingest documents into the knowledge space?"
- "What style policies must I follow?"

After the LLM has populated the graph (a class is "selected"), chips become contextual:
- "Show callers of `<selected>`"
- "Show tests for `<selected>`"
- "Find docs for `<selected>`"
- "Generate a similar tool"
- "What concepts does `<selected>` embody?"

## Inspect panel — six tabs

All tabs lazy-render. Empty state on each tab is the friendly "ask the assistant about X" pointer.

### 1. Graph (centerpiece)

Interactive class+concept graph. Driven by tool-call results emitted as `code_core.graph` artifacts.

**Node categories** (color + shape):
- `Class` — blue rectangle. Package-prefix coded.
- `Concept` (`Semantic kind=concept`) — gold rounded rectangle.
- `StylePolicy` (`Semantic kind=policy`) — purple rounded rectangle.
- `DocSection` — white paper icon.
- `Module` — grey rectangle (collapsed-by-default).

**Edge styles** (color + dash):
- `INHERITS` — solid blue arrow.
- `EMBODIES` (class → concept) — dashed gold.
- `GOVERNED_BY` (class → policy) — dashed purple.
- `RELATED_TO` (concept ↔ concept) — solid gold.
- `CALLS` (method → method) — thin grey.
- `DOCUMENTED_BY` — dotted, paper icon.

**Interactions**:
- Click node → loads `class_footprint` (or `define` for Concept/Policy nodes) and switches to the matching tab.
- "+" on node → expand callers (`find_references`) or callees (`trace_call_chain` depth=1).
- Search box → fuzzy `code_search`.
- "Pin" → keeps node when graph re-roots.
- Toolbar: zoom, fit, reset, scope filter (uses left scope picker).

**Empty state**: *"Ask me about a class — e.g. 'show me BaseEntrypoint and what extends it' — and I'll draw the graph here."*

### 2. Concept

Renders when the LLM emits a `code_core.concept` artifact, or when the user clicks a Concept/StylePolicy node in the graph.

Shows:
- Header: `name`, `kind` badge (concept / policy / term), scope badge (`framework` or `<bundle id>`), aliases.
- `summary` — top, prominent.
- `definition` — long-form markdown.
- For `kind=policy`: `rationale` + `how_to_apply` + `pitfalls` rendered as separate sections.
- Related concepts — chip row, each chip clickable to navigate.
- Realized by (concepts) / Applied to (policies) — collapsible list of qualified_names; click → load `class_footprint` for that symbol.

### 3. Footprint

Structural class card. Renders when a `code_core.footprint` artifact is emitted or after a graph-node click.

Sections:
- Header: name, qualified_name, file path (clickable to Source tab), `is_abstract` badge.
- Docstring.
- **Concepts** — badge row from the augmented `class_footprint` payload (always present now).
- **Style policies** — badge row.
- Inheritance: ancestors / descendants / interfaces.
- Methods table: name, signature, async badge.
- Callers / Callees: collapsible.
- Linked docs / Tests.

### 4. Source

Code snippet for a selected method or class. Renders on demand (`code_core.source` artifact). Read-only Monaco-style block with syntax highlighting + copy button.

### 5. Config drafts

Generated YAML/JSON the assistant produces (e.g. a `bundle_props.yaml` for the dev's new bundle, a `tools_descriptor.py` snippet, a frontmatter-shaped `concept.md`).

Each draft (one `code_core.config_draft` artifact per draft) shows:
- Filename + target path (e.g. `app/ai-app/services/.../my-bundle/concepts/customer.md`).
- Code block with syntax highlighting.
- Two buttons: **Copy** (always) and **Apply** (deferred to v1.1; for now just copy).

### 6. My Bundle

Lists Semantic nodes scoped to the developer's bundle (i.e. `<bundle>/concepts/*.md` files). Empty state: *"Author concepts here to teach your bundle's vocabulary to the LLM and the assistant."*

This tab makes the bundle-scoped vocabulary visible and editable from inside the assistant — closes the loop on the framework's per-bundle vocab extension.

## State management

Two new Redux slices, isolated from the generic chat:

```ts
// configAssistantChatSlice — messages/conversations for THIS page only
{
  conversations: { [id: string]: Conversation },
  activeConversationId: string | null,
  messages: Message[],
  status: "idle" | "streaming" | "error",
  error: string | null,
}

// configAssistantUiSlice — UI state for THIS page only
{
  scope: { packageFilter: string },
  inspect: {
    activeTab: "graph" | "concept" | "footprint" | "source" | "config" | "my_bundle",
    selectedQualifiedName: string | null,
    selectedConceptId: string | null,
    pinnedNodes: string[],
  },
  graph: {
    nodes: GraphNode[],
    edges: GraphEdge[],
    layoutSeed: number,
  },
  configDrafts: ConfigDraft[],
  chipsExpanded: boolean,
}
```

Both register in `app/store.ts` alongside existing slices.

Bundle-scoped concept visibility: **always shown, with a scope badge**. Hiding bundle vocab outside the bundle defeats the assistant's purpose. The badge keeps the developer aware of where each definition came from.

## Backend contract

The `react.code` bundle (now in `mode=config_assistant`) emits artifacts via the existing `chat_artifact` SSE event channel. Each is a separate artifact type rendered by a `logExtensions` registry entry:

| Artifact type | Payload (JSON) | Renders to |
|---|---|---|
| `code_core.graph` | `{nodes: GraphNode[], edges: GraphEdge[], focus: qualified_name}` | Graph tab |
| `code_core.concept` | full `Semantic` record (from `define`) | Concept tab |
| `code_core.footprint` | augmented `class_footprint` payload (incl. `concepts`, `style_policies`) | Footprint tab |
| `code_core.source` | `{qualified_name, file_path, line_start, line_end, language, content}` | Source tab |
| `code_core.config_draft` | `{filename, target_path, language, content}` | Config drafts tab |

Registration follows the existing pattern in `chat-web-app/src/main.tsx` (`addChatLogExtension(artifactType, component)`).

The bundle distinguishes the page via `payload.mode = "config_assistant"` sent on every chat request. The bundle's orchestrate node reads this from `state["search_settings"]` (already wired in Phase 1) or from a new `state["mode"]` field, and:
- Selects the Configuration Assistant system prompt.
- Whitelists the relevant tools: `code_search`, `class_footprint`, `define`, `find_siblings`, `find_references`, `trace_call_chain`, `find_entry_points`, `find_docs_for_code`, `impact_analysis`, `show_architecture`, `show_contract`, plus its existing KB tools.
- Emits the new artifact types when tool results warrant a UI panel (the LLM is instructed to produce `<channel:canvas>` blocks of these shapes).

## MCP tool surface

The bundle, talking to coding-core MCP at `bolt://kdcube-neo4j:7687` (in-container), uses:

- **`define(term, scope?)`** — primary lookup tool. Resolves "what's a Bundle?" to the canonical Concept record.
- **`class_footprint(qualified_name)`** — augmented to include `concepts` + `style_policies`.
- **`code_search(query, search_type, limit)`** — hybrid search across both code symbols and Semantic nodes.
- **`find_siblings`, `find_references`, `trace_call_chain`** — for structural exploration.
- **`show_architecture(package_filter)`** — for the scope picker / overview.
- **`find_docs_for_code`, `find_entry_points`, `impact_analysis`, `show_contract`** — supplementary.

## Resolved decisions (from the earlier design pass)

| Decision | Final answer |
|---|---|
| Page name | Configuration Assistant |
| Conversation isolation | Separate (own slice, own conversation list) |
| Inspect panel v1 | Interactive class+concept graph (centerpiece) — confirmed |
| Quick chip behavior | Tap fills composer; Enter sends |
| Bundle-scoped concept visibility | Always shown, scope badge |
| "My Bundle" tab | Included (6th tab) |
| Persona | Bundle developer |
| Underlying bundle | Reuse `react.code` with mode hint |

## Out of scope for v1

- Apply-config button on `code_core.config_draft` artifacts (writes to user's working dir).
- Diffing bundle scaffolds against existing files.
- Multi-tab graph (compare two classes side-by-side).
- Slash-commands inside composer.
- Mobile / narrow-viewport layout.
- Top-nav entry (direct URL only).
- A dedicated `react.config` bundle (reuse `react.code` for now).

## Implementation order (when we start coding)

1. **Backend** — pipe `mode=config_assistant` through `state` → orchestrate node → system prompt swap. Wire emission of the new `code_core.*` artifact types from the bundle's tool-result handlers. (Half a day.)
2. **FE state + page shell** — slices, route, `ConfigAssistantPage.tsx`, header, conversation list, composer (no inspect panel yet, no chips). Smoke-test that messages flow round-trip. (Half a day.)
3. **Inspect panel skeleton** — tab bar, lazy components, empty states. Wire `Footprint`, `Concept`, `Source`, `Config drafts` first (text-only, no graph). (One day.)
4. **Quick action chips**. (Quarter day.)
5. **Graph tab** — pick a graph lib (`@xyflow/react` is the obvious choice given the existing React 19 stack), implement node/edge styles + interactions. (One to two days.)
6. **My Bundle tab + scope picker**. (Half a day.)
7. **Polish / acceptance test against the flagship task** (build a doc-RAG bundle scaffold end-to-end). (One day.)

Total: ~5 working days for v1.
