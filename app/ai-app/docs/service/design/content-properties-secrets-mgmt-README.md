---
id: ks:docs/service/design/content-properties-secrets-mgmt-README.md
title: "Properties and Secrets Management Design"
summary: "Concrete target design for persistent bundle props, user props, deployment-scoped bundle secrets, and their export/apply flow across local and ECS deployments."
tags: ["service", "design", "props", "secrets", "postgres", "aws-sm", "deployment"]
keywords: ["bundle props", "user props", "bundle secrets", "aws secrets manager", "bundles.yaml", "bundles.secrets.yaml", "redis cache", "control plane"]
see_also:
  - ks:docs/sdk/bundle/bundle-props-secrets-README.md
  - ks:docs/service/configuration/bundle-configuration-README.md
  - ks:docs/service/secrets/secrets-service-README.md
---
# Properties and Secrets Management Design

## 1. Problem to solve

Today the system has drift in ECS:

- **bundle props** written by the admin UI/API live only in Redis
  - key format:
    `kdcube:config:bundles:props:{tenant}:{project}:{bundle_id}`
- **bundle secrets** written by the admin UI/API go to the active secrets backend
  - for ECS this is usually AWS Secrets Manager
- **deployment** still takes secret YAML blobs from GitHub Secrets and pushes them
  into AWS Secrets Manager in `ecs-provision.yml`

That means:

1. bundle props written during operations are not durable enough
2. bundle secrets written during operations are durable, but can be overwritten by the next deploy
3. the human-readable descriptor files and the live runtime state diverge

This document defines the target model that removes that drift.

## 2. Design goals

The system must satisfy all of these:

1. **One source of truth per data class**
2. **No GitHub Secrets as steady-state source for structured config**
3. **No system freeze required before export**
4. **Portable descriptor format remains**
5. **No vendor lock for the interface**
6. **ECS and single-node use the same logical model**

## 3. Exact data classes

We split the data into four classes.

### 3.1 Deployment descriptors

- `assembly.yaml`
- `gateway.yaml`
- `bundles.yaml`
- `bundles.secrets.yaml`
- `secrets.yaml`

These are the human-readable import/export artifacts.

### 3.2 Deployment-scoped bundle props

Examples:

- `execution.runtime`
- `mcp.services`
- `economics.reservation_amount_dollars`
- bundle feature flags
- bundle integration endpoints

Scope:

- tenant
- project
- bundle

These are set by:

- descriptor apply
- bundle admin UI/API

These must survive restart and deploy.

### 3.3 User-scoped bundle props

Examples:

- per-user bundle preferences
- user-specific workflow configuration
- user-owned bundle options

Scope:

- tenant
- project
- bundle
- user

These are set by:

- authenticated user APIs
- bundle-owned code paths

These are **not** deployment descriptors and must never be exported into
`bundles.yaml`.

### 3.4 Secrets

There are two secret scopes:

- deployment-scoped secrets
  - platform secrets
  - bundle secrets
- user-scoped secrets

Deployment-scoped secrets may be represented in:

- `secrets.yaml`
- `bundles.secrets.yaml`

User secrets must **not** be exported into deployment descriptors.

## 4. Source of truth matrix

This is the exact target state.

| Data class | Scope | Source of truth | Exported to descriptor? | Cached in Redis? |
|---|---|---|---|---|
| `assembly.yaml` fields | deployment | deployment config repo / deployment input | yes | no |
| bundle registry + descriptor config | tenant/project/bundle | deployment config repo + apply pipeline | yes, `bundles.yaml` | yes |
| deployment-scoped bundle props overrides | tenant/project/bundle | Postgres `kdcube_control_plane.bundle_props_state` | yes, `bundles.yaml` | yes |
| user-scoped bundle props | tenant/project/bundle/user | Postgres `kdcube_control_plane.user_bundle_props_state` | no | yes |
| deployment-scoped platform secrets | deployment | active secrets backend | yes, `secrets.yaml` if managed in export flow | no |
| deployment-scoped bundle secrets | tenant/project/bundle | active secrets backend | yes, `bundles.secrets.yaml` | no |
| user-scoped secrets | tenant/project/bundle/user | active secrets backend | no | optional metadata only |

**Redis is cache only.**

**GitHub Secrets are not a source of truth for structured descriptors.**

## 5. Exact backend choices

### 5.1 Props

Props are persisted in Postgres.

Schema:

- `kdcube_control_plane`

Reason:

- already deployed by `Dockerfile_PostgresSetup`
- already created before project schemas
- stable across ECS and local
- not vendor-specific

### 5.2 Secrets

Secrets remain behind the existing secrets-manager abstraction.

The active provider is already one of:

- `secrets-file`
- `aws-sm`
- `secrets-service`
- `in-memory`

For persistence, the only valid steady-state providers are:

- `secrets-file`
- `aws-sm`

Target rule:

- if provider is `secrets-file`, the YAML files are the source of truth
- if provider is `aws-sm`, AWS Secrets Manager is the source of truth

No new custom secrets backend is introduced in this design.

## 6. Postgres schema to add

Add these tables to:

- `app/ai-app/src/kdcube-ai-app/kdcube_ai_app/ops/deployment/sql/control_plane/deploy-kdcube-control-plane.sql`

### 6.1 Deployment-scoped bundle props

```sql
CREATE TABLE IF NOT EXISTS kdcube_control_plane.bundle_props_state (
    tenant         TEXT        NOT NULL,
    project        TEXT        NOT NULL,
    bundle_id      TEXT        NOT NULL,
    props          JSONB       NOT NULL DEFAULT '{}'::jsonb,
    revision       BIGINT      NOT NULL DEFAULT 1,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by     TEXT        NOT NULL,
    source         TEXT        NOT NULL,
    PRIMARY KEY (tenant, project, bundle_id)
);

CREATE INDEX IF NOT EXISTS idx_cp_bundle_props_tp
    ON kdcube_control_plane.bundle_props_state (tenant, project);
```

Allowed `source` values:

- `descriptor-apply`
- `admin-api`
- `migration`

### 6.2 Deployment-scoped bundle props audit

```sql
CREATE TABLE IF NOT EXISTS kdcube_control_plane.bundle_props_audit (
    audit_id       UUID        NOT NULL DEFAULT gen_random_uuid(),
    tenant         TEXT        NOT NULL,
    project        TEXT        NOT NULL,
    bundle_id      TEXT        NOT NULL,
    revision       BIGINT      NOT NULL,
    props          JSONB       NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by     TEXT        NOT NULL,
    source         TEXT        NOT NULL,
    PRIMARY KEY (audit_id)
);

CREATE INDEX IF NOT EXISTS idx_cp_bundle_props_audit_lookup
    ON kdcube_control_plane.bundle_props_audit (tenant, project, bundle_id, revision DESC);
```

### 6.3 User-scoped bundle props

```sql
CREATE TABLE IF NOT EXISTS kdcube_control_plane.user_bundle_props_state (
    tenant         TEXT        NOT NULL,
    project        TEXT        NOT NULL,
    bundle_id      TEXT        NOT NULL,
    user_id        TEXT        NOT NULL,
    props          JSONB       NOT NULL DEFAULT '{}'::jsonb,
    revision       BIGINT      NOT NULL DEFAULT 1,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by     TEXT        NOT NULL,
    source         TEXT        NOT NULL,
    PRIMARY KEY (tenant, project, bundle_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_cp_user_bundle_props_tp
    ON kdcube_control_plane.user_bundle_props_state (tenant, project, bundle_id);
```

Allowed `source` values:

- `user-api`
- `bundle-code`
- `migration`

### 6.4 User-scoped bundle props audit

```sql
CREATE TABLE IF NOT EXISTS kdcube_control_plane.user_bundle_props_audit (
    audit_id       UUID        NOT NULL DEFAULT gen_random_uuid(),
    tenant         TEXT        NOT NULL,
    project        TEXT        NOT NULL,
    bundle_id      TEXT        NOT NULL,
    user_id        TEXT        NOT NULL,
    revision       BIGINT      NOT NULL,
    props          JSONB       NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by     TEXT        NOT NULL,
    source         TEXT        NOT NULL,
    PRIMARY KEY (audit_id)
);

CREATE INDEX IF NOT EXISTS idx_cp_user_bundle_props_audit_lookup
    ON kdcube_control_plane.user_bundle_props_audit (tenant, project, bundle_id, user_id, revision DESC);
```

## 7. Runtime behavior

### 7.1 Bundle props read path

Effective bundle props become:

1. bundle code defaults
2. descriptor config from `bundles.yaml`
3. persisted override from `bundle_props_state`

Redis remains only the fast cache for layer 3.

Read sequence:

1. read Redis key
   - `kdcube:config:bundles:props:{tenant}:{project}:{bundle_id}`
2. on cache miss, read `kdcube_control_plane.bundle_props_state`
3. repopulate Redis
4. merge onto descriptor config

### 7.2 Bundle props write path

`POST /admin/integrations/bundles/{bundle_id}/props` must change from:

- Redis-only write

to:

1. upsert `bundle_props_state`
2. insert `bundle_props_audit`
3. update Redis cache
4. publish existing props-update pubsub event

`reset-code` must:

1. replace `bundle_props_state.props` with code defaults
2. bump revision
3. audit
4. refresh Redis

### 7.3 User props runtime path

Add SDK helpers:

- `get_user_prop(key, default=None)`
- `set_user_prop(key, value)`
- `delete_user_prop(key)`

Add authenticated REST path for current user:

- `GET /bundles/{tenant}/{project}/{bundle_id}/user-props`
- `POST /bundles/{tenant}/{project}/{bundle_id}/user-props`

Add admin path:

- `GET /admin/integrations/bundles/{bundle_id}/user-props`
- `POST /admin/integrations/bundles/{bundle_id}/user-props`

Storage rule:

- Postgres is authoritative
- Redis caches per `(tenant, project, bundle_id, user_id)`

Cache key:

```text
kdcube:config:bundles:user-props:{tenant}:{project}:{bundle_id}:{user_id}
```

### 7.4 Secrets runtime path

No storage redesign here.

Bundle secrets and user secrets continue to use the active secrets provider.

Write path stays:

- bundle admin secret writes -> provider
- user secret writes -> provider

Metadata keys stay:

- `bundles.<bundle_id>.secrets.__keys`
- `users.<user_id>.bundles.<bundle_id>.secrets.__keys`

These metadata keys are required for export.

## 8. Descriptor export/apply model

This is the exact rule:

- descriptors are **human-readable import/export artifacts**
- they are **not** the steady-state source of truth in ECS

### 8.1 Export command

Add:

```bash
kdcube config export \
  --tenant <tenant> \
  --project <project> \
  --out <dir> \
  --assembly-in <path-to-current-assembly>
```

Export behavior:

- `assembly.yaml`
  - copied from `--assembly-in`
  - runtime does not mutate it in phase 1
- `bundles.yaml`
  - take deployment bundle registry/config baseline
  - overlay current `bundle_props_state.props`
  - do not include user props
- `bundles.secrets.yaml`
  - read bundle secret keys from provider metadata
  - reconstruct grouped YAML
  - do not include user secrets
- `state-lock.json`
  - export revisions and hashes for conflict detection

`state-lock.json` must include:

- `bundle_props_state.revision` per bundle
- SHA-256 hash per exported bundle secret key

### 8.2 Apply command

Add:

```bash
kdcube config apply \
  --tenant <tenant> \
  --project <project> \
  --from <dir>
```

Apply behavior:

- `assembly.yaml`
  - not written into runtime state in phase 1
  - deployment-owned only
- `bundles.yaml`
  - writes deployment-scoped bundle props into `bundle_props_state`
  - refreshes Redis cache
- `bundles.secrets.yaml`
  - writes bundle secrets into the active secrets provider

Conflict rule:

- if current `bundle_props_state.revision` differs from exported revision -> fail
- if current secret hash differs from exported hash -> fail
- `--force` is the only allowed overwrite bypass

This removes the need to stop the system before export.

## 9. Descriptor storage location

Do **not** email descriptors.

Do **not** store structured descriptor blobs in GitHub Secrets.

Target storage location:

- one private config repository

Recommended layout:

```text
kdcube-config/
  environments/
    prod/
      assembly.yaml
      gateway.yaml
      bundles.yaml
      bundles.secrets.yaml
      state-lock.json
```

Rules:

- `assembly.yaml`, `gateway.yaml`, `bundles.yaml` are plain text in repo
- `bundles.secrets.yaml` is stored encrypted with SOPS/age
- the repo is the operator review surface
- the live authoritative stores remain Postgres and the active secrets backend

## 10. ECS workflow changes

Current problem in:

- `/Users/elenaviter/src/kdcube/kdcube-internal-demo/.github/workflows/ecs-provision.yml`

Today it:

1. reads `SECRETS_YAML` and `BUNDLES_SECRETS_YAML` from GitHub Secrets
2. writes them into AWS Secrets Manager every deploy

That must stop.

### 10.1 Normal ECS deploy

`ecs-provision.yml` must:

- keep using:
  - `assembly.yaml`
  - `gateway.yaml`
  - `bundles.yaml`
- stop syncing secrets to AWS SM by default

Normal deploy must **not** modify:

- deployment-scoped secrets already in AWS SM
- user secrets

### 10.2 New explicit secrets apply workflow

Add a separate workflow:

- `ecs-apply-secrets.yml`

Input:

- checked-out `bundles.secrets.yaml`
- optional `secrets.yaml` if platform-level secret editing is needed later

Behavior:

- run `kdcube config apply --from ...`
- write to AWS SM
- fail on revision/hash mismatch unless `--force`

### 10.3 New export workflow

Add:

- `ecs-export-runtime-config.yml`

Behavior:

- export current `bundles.yaml`
- export current `bundles.secrets.yaml`
- export `state-lock.json`
- commit back to the config repo in a bot PR

This is the human-readable mirror.

## 11. Single-node behavior

### 11.1 `secrets-file`

If provider is `secrets-file`:

- `secrets.yaml` / `bundles.secrets.yaml` are already the live source of truth
- admin writes persist directly into those files

No change required for secret persistence.

### 11.2 Props

Bundle props still move to Postgres for durability and consistency.

So local single-node becomes:

- bundle props source of truth = Postgres
- secrets source of truth = YAML files

This is acceptable because the source is still singular per data class.

## 12. What is exported and what is not

### Exported

- deployment-owned `assembly.yaml`
- deployment-owned `gateway.yaml`
- deployment-scoped bundle config and props in `bundles.yaml`
- deployment-scoped bundle secrets in `bundles.secrets.yaml`

### Not exported

- user props
- user secrets
- bundle storage
- cached indexes
- conversation state
- generated files

That data survives through its own authoritative store and is not deployment input.

## 13. Implementation order

This is the exact order.

### Phase 1

1. add Postgres tables for:
   - `bundle_props_state`
   - `bundle_props_audit`
   - `user_bundle_props_state`
   - `user_bundle_props_audit`
2. change bundle admin props API to write Postgres first, Redis second
3. add Redis read-through from Postgres for bundle props
4. keep secrets provider behavior unchanged

### Phase 2

1. add `kdcube config export`
2. add `kdcube config apply`
3. add `state-lock.json` revision/hash checks
4. add export/apply docs

### Phase 3

1. stop normal ECS deploy from syncing secret YAML into AWS SM
2. add explicit `ecs-apply-secrets.yml`
3. add `ecs-export-runtime-config.yml`
4. move structured descriptor blobs out of GitHub Secrets

### Phase 4

1. add user props SDK + REST APIs
2. wire user props caches
3. keep user props out of deployment export

## 14. Final operating rules

These rules are mandatory.

1. **Redis is cache only**
2. **GitHub Secrets are not the source of truth for structured descriptors**
3. **In ECS, AWS SM is the source of truth for secrets when provider=`aws-sm`**
4. **In local `secrets-file`, YAML files are the source of truth for secrets**
5. **Postgres control-plane tables are the source of truth for bundle props and user props**
6. **User props and user secrets are never exported into deployment descriptors**
7. **Normal deploy must not overwrite persistent runtime secrets**
8. **Descriptor apply is explicit and conflict-checked**

That is the target model.
