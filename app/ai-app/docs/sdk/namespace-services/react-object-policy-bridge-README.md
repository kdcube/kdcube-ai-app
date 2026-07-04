---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/react-object-policy-bridge-README.md
title: "Namespace Services: ReAct Object Policy Bridge"
summary: "How named-service objects, event sources, namespace rehosters, block-production policies, rendering policies, and ReAct pull/read fit together without namespace-specific ReAct code."
status: design
tags: ["sdk", "namespace-services", "react", "block-production", "object-ref", "event-source", "policies"]
updated_at: 2026-06-23
keywords:
  [
    "react.pull",
    "react.read",
    "object_ref",
    "original_object_stats",
    "block production policy",
    "named service provider",
    "event source resolver",
    "artifact namespace rehoster",
    "block.render",
  ]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/ecosystem-component/components-ecosystem-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/react-object-materialization-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/providers-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/clients-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/events/event-subsystem-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/events/namespaces-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/event-source/block-production-README.md
---
# Namespace Services: ReAct Object Policy Bridge

This document defines the policy bridge between ReAct and namespace-owning
providers. It is the contract for objects that are not native ReAct files but
must become usable by an agent through the normal `react.pull` and
`react.read` machinery.

The rule is strict:

```text
Generic ReAct tools carry identity and materialized bytes.
Namespace owners decide object semantics through registered policies.
```

Generic ReAct code must not branch on concrete namespaces such as `cnv`, `mem`,
or `task`. If an object needs special read, stats, render, or announce
behavior, the namespace owner supplies that behavior through the event/source
policy system.

## Boundary

```text
ReAct generic layer
  owns:
    - tool protocol: react.pull, react.read
    - conv:fi: materialized artifact paths
    - pull state mapping: conv:fi: logical_path -> original object_ref
    - generic read target fields:
        object_ref
        logical_path
        physical_path
        mime
        stats_only
        source byte/line metadata
    - policy dispatch by event_source_id

Namespace owner / provider layer
  owns:
    - namespace URI grammar
    - object kind and capabilities
    - object.get byte materialization
    - event_source_id resolution for refs
    - block-production policy for model-visible blocks
    - optional original_object_stats for stats-only reads
    - timeline render patches
    - announce/rendering policy for volatile summaries
```

This boundary keeps ReAct reusable. Canvas can expose board revision stats,
memory can expose memory metadata, and tasks can expose issue metadata without
putting `if namespace == ...` logic into `react.read`.

## End-To-End Flow

```text
User/agent sees an object ref
  object_ref = cnv:main
        |
        v
react.pull(paths=["cnv:main"])
  generic tool:
    asks EventSourceSubsystem for namespace rehoster namespace=cnv
        |
        v
canvas namespace rehoster
  owner code:
    reads current board
    writes JSON snapshot bytes into ReAct artifact storage
    returns:
      object_ref     = cnv:main
      logical_path   = conv:fi:turn_...git/snapshots/cnv/main-....json
      physical_path  = turn_.../git/snapshots/cnv/main-....json
      scope          = snapshots
        |
        v
ReAct pull state
  records:
    conv:fi:turn_...git/snapshots/cnv/main-....json -> cnv:main
        |
        v
react.read(paths=[<fi path>])
  generic tool:
    reads local bytes
    builds a read target with original object_ref and materialized paths
    resolves the owner event_source_id
        |
        v
owner block-production policy
  normal read:
    emits bounded model-visible blocks
  stats_only read:
    emits a block with top-level original_object_stats
        |
        v
Timeline.render()
  applies local projection policies
  optionally calls provider block.render hooks for provider-owned blocks
  optionally renders ANNOUNCE summaries through owner rendering policy
```

## Policy Surfaces

| Surface | Registered by | Called by | Purpose |
| --- | --- | --- | --- |
| `artifact_namespace_rehoster(namespace=...)` | namespace owner | `react.pull` | Materialize a namespace ref into a local `conv:fi:` artifact while preserving `object_ref`. |
| `event_source_resolver(namespace=...)` | namespace owner or named-service adapter | `react.read` owner dispatch | Resolve an `object_ref` to the owner event source when `named_services.<namespace>` is not enough. |
| `event_source_reader(namespace=...)` | namespace owner | runtime/policy code | Resolve a canonical ref to the owner's current structured payload. This is not the model-facing exact-content path. |
| `block_production_policy(...)` | namespace owner | `react.read` | Convert an object/read target into bounded model-visible blocks or stats blocks. |
| `timeline_projection_policy(...)` | namespace owner or local runtime | timeline render | Project stored blocks before prompt rendering. |
| `announce_event_policy(...)` | namespace owner or local runtime | prompt rendering | Add transient ANNOUNCE summaries for volatile/current state. |
| `block.render` named-service operation | provider | prompt renderer or explicit render client | Patch provider-owned blocks or return a direct rendered representation. |

## `original_object_stats`

`react.read(stats_only=true)` normally returns file stats such as MIME, size,
and line count. For materialized namespace objects, the owner can add semantic
stats for the original object.

The owner block-production policy emits those stats as a top-level field on a
produced block:

```json
{
  "type": "react.tool.result",
  "path": "cnv:main",
  "mime": "application/json",
  "text": "{...bounded diagnostic text...}",
  "original_object_stats": {
    "kind": "canvas_snapshot",
    "object_ref": "cnv:main",
    "live_ref": "cnv:main",
    "revision_ref": "cnv:main@416",
    "canvas_name": "main",
    "revision": 416,
    "cards_count": 21,
    "read_snapshot_with": "react.read(paths=['conv:fi:turn_...git/snapshots/cnv/main.json'])",
    "read_latest_with": "react.pull(paths=['cnv:main'])"
  }
}
```

`original_object_stats` is deliberately top-level. It is not hidden inside
`meta`, because `react.read(stats_only=true)` needs a stable, direct owner
contract to copy into the stats response:

```json
{
  "paths": [
    {
      "path": "conv:fi:turn_...git/snapshots/cnv/main.json",
      "status": "stats_only",
      "object_ref": "cnv:main",
      "original_object_stats": {
        "kind": "canvas_snapshot",
        "object_ref": "cnv:main",
        "live_ref": "cnv:main"
      }
    }
  ]
}
```

The shape inside `original_object_stats` is owner-defined. ReAct only copies
the object. It does not interpret canvas counts, memory scores, task status, or
future domain fields.

## Canvas Example

Canvas owns `cnv:` refs. ReAct-visible refs are:

| Ref | Meaning | Agent use |
| --- | --- | --- |
| `cnv:main` | Current live board named `main` for the current user/context. | Use with `react.pull(paths=["cnv:main"])` when the latest board is needed. |
| `cnv:main@416` | Exact board revision 416. | Use only when reasoning about a known revision. |

Internal storage ids such as `cnv:<user_id>:main` are implementation details.
They should not be required in model-facing instructions.

For canvas, the namespace rehoster writes a JSON snapshot into the ReAct
artifact area. On `react.read(stats_only=true)`, the canvas
`canvas.block_production.read_result` policy may read that materialized
snapshot file and emit `original_object_stats` with board counts and recovery
commands. Generic `react.read` only passes the `physical_path`; it does not
know that the object is canvas.

## ANNOUNCE Relationship

Block production and ANNOUNCE solve different problems:

| Mechanism | Lifetime | Owner responsibility |
| --- | --- | --- |
| `react.pull` / `react.read` block production | Timeline-visible read result. | Produce model-visible blocks for a specific object read. |
| `original_object_stats` | One `stats_only` read response. | Summarize the original object enough for the agent to choose the next pull/read. |
| ANNOUNCE rendering policy | Prompt-tail volatile context, bounded by rendering policy. | Expose current/volatile state such as a board map only while relevant. |

Canvas is volatile. A board attached or focused by the user can be rendered in
ANNOUNCE for a bounded number of render rounds. If the agent needs a fresh
exact board after that, it should call `react.pull(paths=["cnv:<name>"])` again
and then read the returned `conv:fi:` path.

The read itself should also leave a compact timeline fact. For canvas that fact
looks like:

```text
[CANVAS TOOL RESULT]
action: read
status: success
canvas_name: main
revision: 416
cards=21 placed=20 floating=1 selected=conv:...
announce_effect: board projection refreshed in ANNOUNCE for 3 render rounds
refresh_rule: use react.pull(paths=['cnv:main']) and react.read on the returned conv:fi: path if you need an updated or prolonged board view
```

The compact fact is timeline history. The board map rendered in ANNOUNCE is
turn-local prompt context.

Owner ANNOUNCE policies should make this lifetime visible in the rendered
section. For example, canvas renders a line like:

```text
visibility: 3/3 render rounds remaining; use react.pull(paths=['cnv:main']) and react.read on the returned conv:fi: path if you need it updated/prolonged.
```

That instruction belongs in the owner policy because only the owner knows
whether a snapshot is volatile, how long it should remain prompt-visible, and
which live object ref refreshes it.

When the same volatile object appears from multiple sources in one turn, the
owner policy should render one ANNOUNCE section for that object. For example,
`chat.canvas.state` can carry a board attached by the UI, and `canvas.read` can
carry a later read of the same board. The source ids describe how the object
arrived; the object ref/revision identify the board.

## Implementation Checklist

For a namespace-owning app/provider:

- Register an `artifact_namespace_rehoster` if the object should be pullable by
  `react.pull`.
- Preserve the canonical `object_ref` in the rehoster result.
- Register an `event_source_resolver` when the namespace needs custom
  URI-to-event-source routing.
- Declare the owner event source with a `block_production` policy.
- In the block-production policy:
  - normal read: emit bounded model-visible blocks;
  - stats-only read: optionally emit a block with top-level
    `original_object_stats`.
- Keep namespace-specific parsing and rendering in the owner module.
- Do not add namespace-specific branches to generic ReAct tools.

This is the same boundary described in
[Object Refs, Presentation, And Actions](object-ref-presentation-and-actions-README.md):
the owner policy may put fields such as `original_object_stats` directly on
the produced block, and generic ReAct code may consume those documented fields
without knowing which provider created them.
