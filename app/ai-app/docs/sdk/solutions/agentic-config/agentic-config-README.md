---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/agentic-config/agentic-config-README.md
title: "Agentic Config: Stored Instruction Sets And The Constructor"
summary: "Agent instructions as managed artifacts: versioned stored sets wired by instr:custom:<id>:<version>, a governed instr namespace, presentation facets, and the constructor widget that browses the block library, renders the final composed instruction, saves immutable versions, and assigns them to application agents."
status: active
tags: ["sdk", "solutions", "agentic-config", "instructions", "agents", "admin", "widget", "named-services"]
updated_at: 2026-07-24
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/system-instruction-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/recipes/kdcube_for_agents/named-services-mcp-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/configuring-agent-service-access/configuring-agent-service-access-README.md
---
# Agentic Config: Stored Instruction Sets And The Constructor

Agents are configured, extended, reconfigured, and tuned — and their SYSTEM
INSTRUCTION moves as fast as their tools and skills. `agentic_config`
(`kdcube_ai_app/apps/chat/sdk/solutions/agentic_config`) makes instruction
sets **managed artifacts**: authored from blocks, stored in immutable
versions with provenance, previewed exactly as an agent receives them, and
wired to any agent by ref.

The composition vocabulary itself (what a `blocks` list may contain, the
predefined profiles, capability-conditional exclusions) is owned by
[the ReAct system-instruction doc](../../agents/react/system-instruction-README.md)
— this page owns the STORE, the namespace, and the authoring surface.

## Stored instruction sets

A stored set is an ordered item list in the composition vocabulary, saved
under a slug id:

- **Ref = wiring ref.** `instr:custom:<id>[:<version>]` is both the object
  ref in the `instr` namespace and the token a descriptor wires. Version
  omitted = latest active.
- **Versions are immutable.** An edit inserts the next version; a ref pinned
  to a version always resolves to the same content. Retiring flips status —
  a PINNED ref keeps resolving even when retired (running agents never
  break); only the unpinned "latest" read filters to active.
- **Provenance is first-class.** Every version records who created it; every
  retire records who and when.
- **Description and tags** make units distinguishable and findable: listing
  supports a `q` substring (id/name/description) and tag containment.
- Storage: the `agentic_instructions` table in the project schema
  (tenant/project-scoped; no cross-project sharing), `items` as JSONB.

At runtime, custom refs expand **asynchronously from the store before
composition** — recursively (stored sets may reference stored sets),
cycle-safe, and fail-open: a ref that cannot resolve is dropped with a
warning, never leaked into a prompt as literal text.

## The block library

The constructor composes from three kinds of units:

1. **Predefined sets** — `instr:profile:full | lite | extra-lite`.
2. **Built-in blocks** — the moderate (`REACT_LITE_*`) and extra-lite
   (`REACT_XLITE_*`) registry blocks. `builtin_block_catalog()` serves each
   with a derived description (the block's own header + first content line)
   and tags: its tier plus, for moderate blocks, every profile that includes
   it. The signal table in the system-instruction doc remains the
   authoritative purpose map.
3. **Stored units** — including "blocks" you author yourself: a stored unit
   whose items are one literal text IS a custom block, composable into other
   sets by ref.

## The `instr` namespace and its governance

`kdcube-services@1-0` registers the `AgenticInstructionsNamedService`
provider: `provider.about`, `object.list` (with `q`/`tags` filters),
`object.get` (one version + history), `object.upsert` (next version),
`object.delete` (retire). Reads are open to the surface's callers; **writes
are admin-gated in the provider** — a widget is never the only gate.

Delegated governance mirrors that: the `instr:read` grant is delegable to
signed-in roles, `instr:write` to super-admin only, with per-operation
grants on the named-services door. **The namespace is deliberately absent
from every agent's `as_consumer` roster** — it serves administrators,
widgets, and governed external clients; an agent sees it only if a roster
explicitly names it.

## The operations facade

The same provider answers the widget through
`kdcube-services@1-0`'s `agentic_instructions` operation
(`body.data.action`):

| action | payload | returns |
| --- | --- | --- |
| `list` | `{include_retired?, q?, tags?}` | latest version per id |
| `blocks` | — | the built-in block catalog |
| `get` | `{ref}` | one version + version history |
| `save` | `{instruction_id, name, description?, tags?, items}` | the next immutable version (admin) |
| `retire` | `{ref}` | retire pinned version / whole id (admin) |
| `preview` | `{items, workspace_implementation?}` | the composed body exactly as the runtime builds it |

The operations route wraps results under the op alias
(`{status: "ok", …, agentic_instructions: {ok, …}}`).

## The constructor widget

Served by `kdcube-services@1-0`
(`sdk://solutions/agentic_config/ui/widget`, admin surface):

- **Block library** — searchable by name, description, or tag across
  predefined sets, built-in blocks, and stored sets (inserted by ref); one
  click appends to the item list.
- **Composed instruction** — rendered CONTINUOUSLY beside the editor
  (debounced server-side compose): the final stitched body an agent
  receives, stored refs expanded.
- **Save as v(n+1)** — immutable versions, provenance echoed back.
- **Assign** — wires a saved set to an application agent: pick the app and
  the agent, and the widget adds/updates an instruction-profile OPTION
  (id = the instruction slug, blocks = the pinned ref) via the platform
  admin props write — user-pickable immediately, optionally as the profile
  default. The write lands live; the descriptor file remains the
  restart-time source of truth.
- **Retire** per version.

Presentation facets (`tool_catalog`, `skills_form`) are the companion picker
surface — profile defaults the user overrides — documented with the
composition vocabulary in the system-instruction doc.
