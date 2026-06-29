# User Memories — Interface

The contract this app exposes: one iframe widget, the memory widget operations
behind it, the `mem` named service, a delegated MCP endpoint, and the storages + dataflows they use. All
operations and the provider come from the SDK memories mixin
(`BaseEntrypointWithEconomicsAndMemory`); this app enables them, it does not
implement them.

## Browser surface

Memories widget (iframe), built from the SDK source:

```
GET /api/integrations/bundles/{tenant}/{project}/user-memories@2026-06-26/widgets/memories
```

The widget receives the standard runtime config (baseUrl, idToken header, tenant,
project, bundleId) and calls the operations below. It is meant to be embedded by
other apps/scenes via iframe — it does not require this app to host a page.

Visibility: `visibility.widget.memories.{user_types,roles}` (default: any
signed-in user).

## Operations (mixin-provided, route="operations")

Authenticated, per signed-in user. POST unless noted.

| Alias | Purpose |
|-------|---------|
| `memories_widget` (GET) | Widget HTML host shell |
| `memories_widget_data` | Search / list the user's memories (scope-filtered) |
| `memories_widget_create` | Create a memory |
| `memories_widget_update` | Update a memory |
| `memories_widget_delete` | Delete a memory |
| `memories_widget_snapshot_*` | Create/list/restore memory snapshots |
| `memories_widget_reconcile_*` | AI-assisted dedup/reconciliation (economics-guarded) |

Scope is governed by config: `memory.widget.default_scope_filter`
(`all_user_memories` here) and `memory.widget.allow_all_user_memories`. Writes
require `memory.widget.allow_write: true`.

## Named service — `mem`

Registered automatically while `memory.enabled: true` (provider from
`kdcube_ai_app.apps.chat.sdk.context.memory.named_service.make_memory_named_service_provider`),
and announced to Redis discovery on load. Other apps consume it instead of
embedding the module:

- Namespace: `mem`
- Refs: `mem:<memory_id>`
- Object ops: `object.search`, `object.get`, `object.create`, `object.update`,
  `object.delete` (write ops gated by the memory write toggle).

## MCP endpoint — `memories`

Public route, platform-managed by Connection Hub delegated credentials:

```text
POST /api/integrations/bundles/{tenant}/{project}/user-memories@2026-06-26/public/mcp/memories
```

Descriptor policy:

```yaml
surfaces:
  as_provider:
    mcp:
      memories:
        auth:
          mode: managed
          authority_id: oauth_mcp
          tools:
            memory_search:
              grants: [memories:read]
            memory_get:
              grants: [memories:read]
          selected_tool_grants: true
```

Tools:

| Tool | Purpose |
|------|---------|
| `memory_search` | Search the approving user's visible memory notes. Reads aggregate across linked identities through `identity_family_resolve` when that user preference is enabled. |
| `memory_get` | Read one visible memory note by id from the same identity-family read scope. |

The MCP access token is an integration credential. The bundle reads memories for
the token's `grantor_subject` from the delegated credential envelope, not for the
derived `integration:claude:*` token subject. Writes are intentionally not
exposed over this MCP endpoint.

## Storages

| Store | Backend | Owner | Contents |
|-------|---------|-------|----------|
| User memories | Postgres (per tenant/project; embeddings for hybrid search) | SDK memory store | The user's memory records, scoped per user. Schema ensured on first widget use (`memory.widget.ensure_schema`). |
| Reconciliation jobs | Bundle artifact storage (`memory/reconciliation/jobs`) | mixin | Dedup/reconcile job state; retention `memory.reconciliation.retention_days`. |
| Memory snapshots | Bundle artifact storage (`memory/snapshots`) | mixin | Point-in-time snapshots; caps via `memory.snapshots.*`. |

This app stores **no domain data of its own** — it only enables the SDK memory
store. Memories are **user-scoped**, not app-scoped, which is why the widget
defaults to `all_user_memories`.

## Dataflows

```text
widget (iframe)
  └─ memories_widget_data / _create / _update / _delete
        └─ SDK memory store (Postgres, per user)  ← read/write
        └─ embeddings for hybrid (lexical+semantic) search

reconcile_* / snapshot_*
  └─ economics guard reserves budget (reconciliation.reservation_amount_dollars)
  └─ artifact storage (jobs / snapshots)

other app's agent
  └─ named service `mem` (object.search/get/create/update/delete)
        └─ same SDK memory store (no module embedding)

external Claude client
  └─ Connection Hub OAuth consent for resource=user-memories MCP URL
        └─ delegated token with memories:read + selected memory_* tools
        └─ public/mcp/memories
              └─ SDK memory store for grantor_subject
```

Auth: per signed-in user (cookie/idToken). The memory store is keyed by the
platform user id, so the same memories appear wherever this app's widget or the
`mem` service is used.
