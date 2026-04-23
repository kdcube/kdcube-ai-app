---
id: ks:docs/configuration/bundles-secrets-descriptor-README.md
title: "Bundles Secrets Descriptor"
summary: "Deployment-scoped bundle secret configuration in bundles.secrets.yaml: per-bundle credentials, integration tokens, and provider-backed bundle secrets across local file mode and AWS."
tags: ["service", "configuration", "bundle", "secrets", "deployment", "descriptor"]
keywords: ["bundle secret inventory", "per-bundle credentials", "integration tokens", "bundle api keys", "deployment-scoped bundle secrets", "local secrets file mode", "aws secrets manager bundle secrets", "bundle secret provider", "bundle secret export path"]
see_also:
  - ks:docs/service/cicd/descriptors-README.md
  - ks:docs/configuration/bundles-descriptor-README.md
  - ks:docs/configuration/secrets-descriptor-README.md
  - ks:docs/configuration/bundle-runtime-configuration-and-secrets-README.md
  - ks:docs/configuration/runtime-configuration-and-secrets-store-README.md
---
# Bundles Secrets Descriptor

`bundles.secrets.yaml` stores deployment-scoped bundle secrets.

Example:

```yaml
bundles:
  version: "1"
  items:
    - id: "user-mgmt@1-0"
      secrets:
        user_management:
          cognito_user_pool_id: null
          sheets_integration_credentials_file_content: null
```

## What it is for

Use this file for bundle-specific secrets such as:

- API keys
- tokens
- private credentials
- integration secrets that belong to one bundle

Do not put these values into:

- `bundles.yaml`
- `assembly.yaml`

## Direct runtime contract from this descriptor

### Supported access APIs

| Need | API | Notes |
|---|---|---|
| secret for the current bundle | `get_secret("b:group.key")` | Expands to `bundles.<current_bundle_id>.secrets.group.key` |
| explicit bundle-scoped secret | `get_secret("bundles.<bundle_id>.secrets.group.key")` | Use when bundle id is known explicitly |

### File-resolution env vars

| Env var | Meaning | Modes |
|---|---|---|
| `BUNDLE_SECRETS_YAML` | Explicit file URI or path for `bundles.secrets.yaml` in `secrets-file` mode | direct local service run |
| `HOST_BUNDLES_SECRETS_YAML_DESCRIPTOR_PATH` | Host file staged into `/config/bundles.secrets.yaml` by the CLI installer | CLI local compose |

### Descriptor fields that matter to runtime

| `bundles.secrets.yaml` field | Used by | Notes |
|---|---|---|
| `bundles.items[].id` | bundle-scoped secret path resolution | must match the bundle id in `bundles.yaml` |
| `bundles.items[].secrets.*` | `get_secret("b:...")` | values are bundle-scoped secret leaves |

## Authority by mode

### CLI local compose

If `assembly.secrets.provider == secrets-file`:

- `bundles.secrets.yaml` is the live file authority
- it is mounted into the runtime

If you use another provider:

- the file is installer input only

### Direct local service run

If `SECRETS_PROVIDER=secrets-file`:

- point the process to the file with `BUNDLE_SECRETS_YAML`
- the file is the live authority

### AWS deployment

In `aws-sm`:

- `bundles.secrets.yaml` is deployment input and export format
- live deployment-scoped bundle secret authority is:
  - `<prefix>/bundles/<bundle_id>/secrets`

## Key rule

- local file mode: `bundles.secrets.yaml` can be the live authority
- AWS `aws-sm` mode: grouped AWS SM bundle docs are the live authority
