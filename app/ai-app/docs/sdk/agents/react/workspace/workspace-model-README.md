---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/workspace/workspace-model-README.md
title: "ReAct Workspace Model"
summary: "Authoritative agent-facing contract for the ReAct per-turn sparse workspace: the [WORKSPACE] ANNOUNCE map (LOCAL material tree + REMOTE git anchor), files/outputs/snapshots/attachments namespaces, logical fi: vs physical paths, and the react.pull / react.checkout / read / rg / write / patch responsibilities."
status: confirmed
tags: ["sdk", "agents", "react", "workspace", "pull", "checkout", "announce", "artifacts"]
keywords:
  [
    "react workspace",
    "each turn starts blank",
    "sparse workspace",
    "[WORKSPACE] announce",
    "local materialized tree",
    "latest committed turn",
    "pull anchor",
    "files vs outputs",
    "react.pull",
    "react.checkout",
    "replace overlay",
    "fi: logical path",
  ]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/workspace/git-backed-workspace-engineering-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/workspace/workspace-lifecycle-and-distribution-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/react-announce-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/react-tools-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/events/namespaces-README.md
---

# ReAct Workspace Model

This is the canonical agent-facing contract for the ReAct workspace: how the
sparse per-turn workspace behaves, how to read its live state from `[WORKSPACE]`
in ANNOUNCE, what the `files/` `outputs/` `snapshots/` `attachments/` namespaces
mean, and how `react.pull` / `react.checkout` / `react.read` / `react.rg` /
`react.write` / `react.patch` cooperate.

- The git engineering (lineage branch, per-turn version refs, isolation, publish
  flow, integration points) is in
  [git-backed-workspace-engineering-README.md](./git-backed-workspace-engineering-README.md).
- The filesystem lifecycle and distributed/Fargate transport are in
  [workspace-lifecycle-and-distribution-README.md](./workspace-lifecycle-and-distribution-README.md).

## The workspace starts blank every turn

A turn runs in its own sparse workspace under `OUTPUT_DIR`. **At the start of
each turn that workspace is empty.** The local *bytes* of anything you
materialized in an earlier turn are not on disk now — files you pulled, checked
out, or wrote, and files your code produced, are all gone. Only the **logical
refs** (`fi:` and registered owner refs) persist across turns; the local files
do not.

This is the single most important rule, and the most common mistake: seeing a
`fi:turn_<old>.files/...` ref in the timeline does **not** mean that file is on
disk this turn. If you did not materialize it *this* turn, it is not local.

Before any local-bytes tool — `exec`/code, `react.rg`, `react.patch`, rendering
tools, file inspection — touches a file this turn, it must be materialized this
turn with `react.pull` (and `react.checkout` for an editable `files/...` tree).

## `[WORKSPACE]` in ANNOUNCE — your live material map

`[WORKSPACE]` is rebuilt every round in ANNOUNCE. It has two clearly separated
views:

- **LOCAL** — exactly what is materialized on disk *this* round. This is the
  only content local-bytes tools can touch directly.
- **REMOTE git branch** — the top-level projects in this conversation's git
  branch that you *could* pull. They are **not** local until pulled.

Treat the LOCAL tree as the source of truth: if a path is not in it, it is not
local — pull it first.

```text
[WORKSPACE]
  current_turn_root: turn_2026-06-22-00-10-13-895/

  LOCAL — materialized on disk THIS turn.
  This is the ONLY content react.read / react.rg / react.patch / exec can touch directly.
  If a path is not in this tree it is NOT local — pull it first, even if you see its fi: ref in the timeline.

  turn_2026-06-22-00-10-13-895/   (current turn · EDITABLE)
    files/
      workspace_app/      — checked out from fi:turn_2026-06-20-18-30-02.files/workspace_app · MODIFIED this turn
    outputs/
      report/summary.md   — produced this turn
    attachments/
      requirements.xlsx   — user upload this turn
    snapshots/            (empty)
  turn_2026-06-20-18-30-02/   (pulled reference · READ-ONLY — checkout into the current turn to edit)
    files/
      analytics_dashboard/

  REMOTE git branch — top-level projects you can pull (NOT local until pulled).
  latest committed turn: turn_2026-06-20-18-30-02
  → pull any project or subpath at its latest by building the ref with THIS turn id:
        fi:turn_2026-06-20-18-30-02.files/<project>[/<subpath>]
    files/workspace_app         [editable in current turn]
    files/analytics_dashboard   [pulled · read-only]
    files/data_pipeline
    files/marketing_site
    files/auth_service
  examples:
    pull a subfolder:  react.pull(paths=["fi:turn_2026-06-20-18-30-02.files/data_pipeline/src/etl"])
    make editable:     react.checkout(mode="replace", paths=["fi:turn_2026-06-20-18-30-02.files/data_pipeline"])
```

### Reading the LOCAL tree

- The tree lists every materialized turn root. The **current turn root** is
  `EDITABLE`. Any other root present is a **READ-ONLY** reference you pulled
  earlier this turn — `checkout` it into the current turn to edit it.
- Under each root, only **top-level** entries are shown per namespace. A
  `files/<project>/` folder is collapsed (no matter how many files it holds);
  `outputs/` and `attachments/` list their actual files (they are few and
  ad-hoc).
- `files/` entries carry provenance: where a project was `checked out from`, and
  whether it has been `MODIFIED this turn`.

### Reading the REMOTE section — the single pull anchor

`files/` is backed by this conversation's git branch. Every committed turn
creates a **version** of the branch; a `fi:turn_<id>.files/<path>` ref reads
`<path>` from *that turn's* version, and pulling a `files/` ref checks it out
from the branch.

To pull the **latest** state of any project — or a subfolder of it — use the one
**latest committed turn** id shown in `[WORKSPACE]` and build the ref:

```text
fi:turn_<latest_committed>.files/<project>[/<subpath>]
```

That single version holds every project at its newest committed state, so the
**same anchor turn id works for all projects** in the list. Do not invent a turn
id and do not use a per-project turn — read the anchor from `[WORKSPACE]`.
Cross-conversation: `fi:conv_<conversation_id>.turn_<latest>.files/...`.

The `[editable in current turn]` / `[pulled · read-only]` tags on REMOTE rows
tell you which projects you have already materialized, and in what mode.

### How this prevents the stale-ref mistake

You see `fi:turn_<old>.files/data_pipeline` in the timeline and want to grep it.
It is **not** in the LOCAL tree, so it is not on disk. The REMOTE list shows
`files/data_pipeline` with no local tag and gives you the anchor turn id. You
build `fi:turn_<latest_committed>.files/data_pipeline`, `react.pull` it, and next
round it appears in LOCAL — then you grep it.

## Namespaces

```text
files/       durable workspace/project state (git-backed; the editable project tree)
outputs/     produced artifacts: reports, exports, render sources, diagnostics, one-off & binary files
snapshots/   story/workflow state snapshots (separate from files/, even when text)
attachments/ user-uploaded files for a turn
external/    externally authored / domain / followup attachments rehosted for ReAct
```

`files/` is the **only** namespace that represents current editable project
state; it is what `react.checkout` populates under `turn_<current>/files/...`,
and it is what is committed to the conversation's git lineage.

`outputs/` is not workspace history. It holds produced artifacts (HTML, Markdown,
JSON, images, PDFs, logs, reports, render sources, test output) — frequently
individual or binary files made for ad-hoc needs. They are deliverables, not the
project tree, and are not committed to git.

`snapshots/` records current story/workflow state (wizard state, canvas state,
user-story state) and is separate from `files/` even when textual.

**Where things go:** when you BUILD or edit a project, it goes under
`turn_<current>/files/<scope>/...` — that is your workspace. Produced
deliverables and one-off artifacts go under `turn_<current>/outputs/<scope>/...`,
never the project itself. If the user asks you to build a project/app, write its
files under `files/`, not `outputs/`.

## Logical refs and physical paths

Logical `fi:` refs are the cross-turn identity; physical `OUTPUT_DIR`-relative
paths are what code, `react.patch`, and rendering tools use.

```text
fi:turn_<id>.files/<rel>                                         -> turn_<id>/files/<rel>
fi:turn_<id>.outputs/<rel>                                       -> turn_<id>/outputs/<rel>
fi:turn_<id>.snapshots/<rel>                                     -> turn_<id>/snapshots/<rel>
fi:turn_<id>.user.attachments/<rel>                              -> turn_<id>/attachments/<rel>
fi:turn_<id>.external.<event_kind>.attachments/<event_id>/<rel>  -> turn_<id>/external/<event_kind>/attachments/<event_id>/<rel>
fi:conv_<conversation_id>.turn_<id>.files/<rel>                  -> conv_<conversation_id>/turn_<id>/files/<rel>
```

`react.read` and `react.pull` take **logical** paths. `react.write`,
`react.patch`, rendering tools, and exec code take **physical** paths. A physical
path passed to `react.read` is a protocol error.

### Visibility is separate from namespace

```text
files/...   + external  -> workspace member also emitted to the user
files/...   + internal  -> workspace member not emitted to the user
outputs/... + external  -> downloadable/visible artifact, not workspace state
outputs/... + internal  -> runtime/agent artifact, not workspace state
```

## `react.pull` vs `react.checkout`

The two tools are deliberately separate. **Pulling materializes; it does not
activate.** **Checkout activates an editable `files/` tree.**

### `react.pull`

Use `react.pull` when bytes must exist locally under `OUTPUT_DIR` for inspection,
search, generated code, or copying. Pulled content lands as **read-only
reference material** under its source turn root (e.g.
`turn_<older>/files/...`); it is not the current editable project.

```text
fi:turn_111.files/app/src/main.py    -> turn_111/files/app/src/main.py
fi:turn_111.outputs/report.html      -> turn_111/outputs/report.html
nmsp:draft_1/issue-draft.yaml        -> returns logical_path/physical_path chosen by the registered rehoster
```

Rules:

- accepts `fi:` refs and registered custom namespace refs (`nmsp:...`);
- `fi:turn_<id>.files/<scope-or-subtree>` may be pulled as a subtree (folder
  pulls are git-tracked text; exact binary refs hydrate point-wise from hosting);
- `fi:turn_<id>.outputs/<file>`, attachments, and external attachments are
  exact-file pulls;
- cross-conversation refs use `fi:conv_<conversation_id>.turn_<id>...` and
  materialize under `conv_<conversation_id>/turn_<id>/...`;
- custom namespace refs are opaque — use the returned `logical_path` /
  `physical_path`, do not derive `fi:` by hand;
- `ev:` refs identify timeline event objects (readable with `react.read` like
  `tc:`); they are **not** artifact refs — do not pass `ev:` to `react.pull`.
  Pull the event's `object_ref`, `hosted_uri`, or an artifact ref inside its
  payload instead.

### `react.checkout`

Use `react.checkout` when historical `files/...` refs should become the current
**editable** project tree.

```json
{ "paths": ["fi:turn_111.files/app"], "mode": "replace" }
```

Rules:

- accepts `fi:...files...` refs only (not `nmsp:`/`cnv:`/`mem:`/`ev:`);
- `mode="replace"` rebuilds `turn_<current>/files/` from the requested refs,
  applied in order;
- `mode="overlay"` keeps the current `files/` tree and applies the requested refs
  on top without deleting unspecified files;
- after checkout, edit/search/run the current copy under
  `turn_<current>/files/...`, never the historical `turn_<older>/...` copy.

To make a custom (`nmsp:`) artifact editable workspace state, pull it first, then
write/copy the intended file explicitly under `turn_<current>/files/...`.

## Tool responsibilities

- **`react.read`** — load context by **logical** path (`fi:`, `ar:`, `tc:`,
  `so:`, `su:`, `sk:`). It does not read `nmsp:` directly — pull first.
- **`react.rg`** — ripgrep-like search over files **already materialized locally**
  this turn. It does not search the timeline, hidden/pruned blocks, owner
  namespaces, or unpulled history. Materialize older files with `react.pull`
  (then `react.checkout` if editing) before searching them.
- **`react.write`** — create/replace a file in a current-turn namespace.
  `files/...` = durable workspace/project state; `outputs/...` = produced
  artifact.
- **`react.patch`** — edit an existing current-turn text file under
  `turn_<current>/files/...` or `turn_<current>/outputs/...` (including
  exec-produced files). It does not require the file to have been created by
  `react.write`, and it does not patch historical `fi:` refs — pull + checkout
  those into the current turn first.

## Custom namespace rehosters

A bundle/module may register an artifact namespace rehoster that bridges
owner-domain refs into the ReAct artifact model:

```python
@artifact_namespace_rehoster(namespace="nmsp")
def rehost(...):
    ...
```

When you `react.pull` such a ref, the rehoster chooses the destination by the
artifact's meaning, writes the bytes under the matching `OUTPUT_DIR` physical
path, and returns an `fi:` logical path plus physical path:

```text
nmsp:draft_1/issue-draft.yaml
  -> fi:turn_<current>.snapshots/nmsp/draft_1/issue-draft.yaml

nmsp:draft_1/evidence/screenshot.png
  -> fi:turn_<current>.external.nmsp.attachments/nmsp_<id>/nmsp/draft_1/evidence/screenshot.png
```

`nmsp` is only an example owner-domain namespace; it is valid only when a bundle
registers `@artifact_namespace_rehoster(namespace="nmsp")`.

## Safe collaboration workflow

The cooperative pattern for working in the sparse workspace:

1. **Read `[WORKSPACE]` first** — see what is already LOCAL and what must be
   pulled.
2. **Discover** the ref from the timeline / REMOTE list.
3. **Pull** it (`react.pull`) using the latest-committed-turn anchor for
   `files/`, then continue from the returned `logical_path` / `physical_path`.
4. **Read / search** the materialized bytes (`react.read`, `react.rg`).
5. **Checkout** (`react.checkout`) if you intend to **edit** a `files/` project,
   so it becomes the editable current-turn tree.
6. **Write / patch** the current copy under `turn_<current>/files/...` (or
   produce deliverables under `turn_<current>/outputs/...`).

Your edits to `files/` are committed to the conversation's git lineage at the end
of the turn (publish). `outputs/` and `snapshots/` use hosted artifact history,
not git.
