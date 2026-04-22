---
id: ks:docs/service/configuration/runtime-read-write-contract-README.md
title: "Runtime Read/Write Contract"
summary: "One-page contract for runtime config and secret helpers: what they read, where they write, and which storage is authoritative in each mode."
tags: ["service", "configuration", "runtime", "helpers", "contract"]
keywords: ["get_settings", "get_secret", "get_plain", "bundle_prop", "set_bundle_prop", "set_bundle_secret", "get_user_secret"]
see_also:
  - ks:docs/service/configuration/service-config-README.md
  - ks:docs/service/configuration/assembly-descriptor-README.md
  - ks:docs/service/configuration/bundles-descriptor-README.md
  - ks:docs/service/configuration/bundles-secrets-descriptor-README.md
  - ks:docs/service/configuration/secrets-descriptor-README.md
---
# Runtime Read/Write Contract

This page is the single runtime contract for the main configuration and secret
helpers used by platform code and bundle code.

It answers:

- what each helper reads
- whether it reads effective runtime state or raw descriptor files
- where writes go
- what is authoritative in local file mode vs AWS `aws-sm`

## Rule of thumb

- use `get_settings()` for effective typed platform/runtime settings
- use `get_plain(...)` only for raw descriptor inspection
- use `get_secret(...)` for deployment-scoped secrets
- use `self.bundle_prop(...)` for effective deployment-scoped bundle config
- use `get_user_prop(...)` / `get_user_secret(...)` for per-user state

## Prohibited direct access in feature and bundle code

Do not bypass the helper contract in normal feature code or bundle code.

Prohibited patterns:

- `os.getenv(...)` or `os.environ[...]` for deployment-owned config or secrets
- direct `get_secrets_manager(...).get_secret(...)` calls
- direct file opens of descriptor YAML files through hardcoded paths

Use instead:

- `get_settings()` for effective typed runtime settings
- `get_secret(...)` for deployment-scoped secrets
- `get_plain(...)` for raw descriptor inspection
- `self.bundle_prop(...)` for effective bundle config

The only normal exception for direct env reads is code that intentionally lives
at the iso-runtime or sandbox boundary and is explicitly designed to be driven
by process env.

Why direct descriptor file path reads are prohibited:

- it hardcodes one runtime filesystem layout
- it bypasses descriptor path indirection such as `PLATFORM_DESCRIPTORS_DIR`,
  `ASSEMBLY_YAML_DESCRIPTOR_PATH`, and `BUNDLES_YAML_DESCRIPTOR_PATH`
- it makes local runs, tests, and alternative mount layouts easier to break
- it bypasses the documented helper contract and any future mode-specific
  resolution logic

## Read helpers

| Helper | Reads | Scope | Authority today | Notes |
|---|---|---|---|---|
| `get_settings()` | effective typed runtime settings | platform/runtime | promoted config assembled from env, descriptors, and configured secrets provider | use for ports, auth ids, storage backends, promoted infra/auth secret-backed fields |
| `get_plain("...")` / `read_plain("...")` | raw `assembly.yaml` value | platform/runtime | mounted or explicitly addressed descriptor file | no Redis/provider overrides, no write path |
| `get_plain("b:...")` / `read_plain("b:...")` | raw `bundles.yaml` value | deployment + bundle | mounted or explicitly addressed descriptor file | raw descriptor only, not effective bundle runtime state |
| `get_secret("canonical.key")` / `read_secret("canonical.key")` | deployment-scoped platform/global secret | deployment | configured secrets provider | accepts canonical dot keys; env aliases are compatibility inputs, not the stable contract |
| `get_secret("b:group.key")` | deployment-scoped bundle secret | deployment + bundle | configured secrets provider | expands to `bundles.<bundle_id>.secrets.group.key` |
| `self.bundle_prop("dot.path")` | effective deployment-scoped bundle prop | deployment + bundle | Redis-backed effective bundle props, with descriptor/provider backfill | this is not a raw `bundles.yaml` read |
| `self.bundle_props` | full effective bundle prop tree | deployment + bundle | same as `self.bundle_prop(...)` | merged code defaults + deployment overrides |
| `get_user_prop(...)` | user-scoped non-secret bundle state | deployment + bundle + user | PostgreSQL user bundle props table | never exported to descriptors |
| `get_user_props()` | all user-scoped non-secret bundle props | deployment + bundle + user | PostgreSQL user bundle props table | same scope as `get_user_prop(...)` |
| `get_user_secret(...)` | user-scoped bundle secret | deployment + bundle + user | configured secrets provider | never exported to descriptors |

## Write helpers

| Helper | Writes | Scope | Persistence target today | Export behavior |
|---|---|---|---|---|
| `await set_bundle_prop("dot.path", value)` | deployment-scoped bundle prop | deployment + bundle | Redis first; then mounted `bundles.yaml` if present, otherwise grouped bundle descriptor doc in `aws-sm` | deployment-scoped bundle props are exported to `bundles.yaml` |
| `await set_bundle_secret("dot.path", value)` | deployment-scoped bundle secret | deployment + bundle | configured secrets provider | exported to `bundles.secrets.yaml` only when provider/export flow supports it; in `aws-sm` live authority is provider state |
| `set_user_prop(...)` | user-scoped non-secret bundle state | deployment + bundle + user | PostgreSQL user bundle props table | never exported |
| `delete_user_prop(...)` | deletes user-scoped non-secret bundle state | deployment + bundle + user | PostgreSQL user bundle props table | never exported |
| `set_user_secret(...)` | user-scoped bundle secret | deployment + bundle + user | configured secrets provider | never exported |
| `delete_user_secret(...)` | deletes user-scoped bundle secret | deployment + bundle + user | configured secrets provider | never exported |

## What "effective" means

There are two very different categories of reads:

### Effective runtime reads

These helpers read the state the runtime is actually meant to use:

- `get_settings()`
- `get_secret(...)`
- `self.bundle_prop(...)`
- `get_user_prop(...)`
- `get_user_secret(...)`

These helpers may read from:

- env vars
- descriptor-backed settings
- Redis-backed effective bundle state
- PostgreSQL user state
- configured secrets provider

### Raw descriptor reads

These helpers read the descriptor file as a file:

- `get_plain(...)`
- `read_plain(...)`

They do not:

- merge code defaults
- include Redis overrides
- include user state
- persist changes anywhere

## Mode-specific authority

### CLI local compose

| Data class | Authority |
|---|---|
| platform/runtime non-secret config | staged descriptors under `/config`, plus env |
| deployment-scoped bundle props | mounted `bundles.yaml`, with Redis as runtime cache |
| deployment-scoped bundle secrets | `bundles.secrets.yaml` only when `secrets-file` is active; otherwise configured provider |
| platform/global secrets | `secrets.yaml` only when `secrets-file` is active; otherwise configured provider |
| user props | PostgreSQL |
| user secrets | configured secrets provider |

### Direct local service run

| Data class | Authority |
|---|---|
| platform/runtime non-secret config | files and env passed explicitly to the process |
| deployment-scoped bundle props | mounted/explicit `bundles.yaml`, with Redis runtime cache if used |
| deployment-scoped bundle secrets | `bundles.secrets.yaml` in `secrets-file` mode, otherwise configured provider |
| platform/global secrets | `secrets.yaml` in `secrets-file` mode, otherwise configured provider |
| user props | PostgreSQL |
| user secrets | configured secrets provider |

### AWS deployment (`aws-sm`)

| Data class | Authority |
|---|---|
| platform/runtime non-secret config | deployment env + descriptor-backed runtime snapshots |
| deployment-scoped bundle props | Redis effective state, backfilled from mounted `bundles.yaml` or grouped bundle descriptor doc |
| deployment-scoped bundle secrets | `<prefix>/bundles/<bundle_id>/secrets` |
| platform/global secrets | mixed provider contract: grouped `platform/secrets` plus canonical per-key fallback where still used |
| user props | PostgreSQL |
| user secrets | configured secrets provider under user-scoped keys |

## Current bundle prop write behavior

`set_bundle_prop(...)` is not "write one Redis key and stop".

Current behavior:

1. write the effective prop update into Redis
2. if mounted `bundles.yaml` exists, persist the change into that file
3. otherwise, in `aws-sm`, persist the change into the grouped deployment bundle descriptor doc

That is why `self.bundle_prop(...)` should be treated as effective deployment
config, not as a raw file read.

## Current secret read behavior

`get_secret(...)` should be used with canonical keys:

- `services.openai.api_key`
- `services.git.http_token`
- `auth.oidc.admin_password`
- `b:external.api_key`

Runtime compatibility with env alias names still exists, but the stable
contract is the canonical dot path.

In `aws-sm` today:

- bundle deployment secrets are grouped per bundle
- platform/global secret reads may resolve through grouped docs or canonical
  per-key fallback paths depending on the secret class

So `aws-sm` is not "one single JSON blob for everything".

## Practical helper selection

| Need | Use |
|---|---|
| port, auth id, storage backend, runtime toggle | `get_settings()` |
| raw `assembly.yaml` inspection | `get_plain("...")` |
| raw `bundles.yaml` inspection | `get_plain("b:...")` |
| platform/global deployment secret | `get_secret("canonical.key")` |
| deployment-scoped bundle secret | `get_secret("b:...")` |
| effective deployment-scoped bundle config | `self.bundle_prop(...)` |
| per-user non-secret bundle state | `get_user_prop(...)` / `set_user_prop(...)` |
| per-user secret bundle state | `get_user_secret(...)` / `set_user_secret(...)` |

## Important non-rules

- `get_plain(...)` is not a configuration write API
- `self.bundle_prop(...)` is not a raw descriptor read
- user props/secrets are not exported back into descriptors
- deployment-scoped bundle props/secrets are operational config, not ordinary business data
- direct hardcoded descriptor file path reads are not part of the supported
  runtime contract
- direct secrets-provider calls are not part of the supported runtime contract
- raw env access for deployment-owned config is not part of the supported
  runtime contract outside explicit iso-runtime/sandbox boundary code

## Related pages

- [service-config-README.md](service-config-README.md)
- [assembly-descriptor-README.md](assembly-descriptor-README.md)
- [bundles-descriptor-README.md](bundles-descriptor-README.md)
- [bundles-secrets-descriptor-README.md](bundles-secrets-descriptor-README.md)
- [secrets-descriptor-README.md](secrets-descriptor-README.md)
