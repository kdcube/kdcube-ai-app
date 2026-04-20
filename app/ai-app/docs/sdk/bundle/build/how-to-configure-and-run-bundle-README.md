---
id: ks:docs/sdk/bundle/build/how-to-configure-and-run-bundle-README.md
title: "How To Configure And Run A Bundle"
summary: "Practical guide for using KDCube with bundle descriptors, local path bundles, git bundles, bundle props/secrets, and the local runtime workflow."
tags: ["sdk", "bundle", "configuration", "runtime", "cli", "bundles.yaml"]
keywords: ["how to configure bundle", "bundle runtime", "bundles.yaml", "bundles.secrets.yaml", "assembly.yaml", "kdcube build upstream", "kdcube info"]
see_also:
  - ks:docs/service/configuration/bundles-descriptor-README.md
  - ks:docs/service/configuration/bundles-secrets-descriptor-README.md
  - ks:docs/service/configuration/assembly-descriptor-README.md
  - ks:docs/sdk/bundle/build/how-to-write-bundle-README.md
  - ks:docs/sdk/bundle/build/how-to-test-bundle-README.md
  - ks:docs/sdk/bundle/bundle-dev-README.md
  - ks:docs/sdk/bundle/bundle-props-secrets-README.md
---
# How To Configure And Run A Bundle

This page is for the operational side of bundle work:

- where to put bundle definitions
- how `kdcube` uses the runtime workdir
- how to test a local bundle from your source tree
- what to change when a bundle moves between local path and git
- what happens when props or secrets are changed

Use this page when you are working with:

- `assembly.yaml`
- `bundles.yaml`
- `bundles.secrets.yaml`
- `kdcube --build --upstream`
- `kdcube --info`
- `kdcube --bundle-reload`

Use other docs for the exact descriptor schemas:

- [bundles-descriptor-README.md](../../../service/configuration/bundles-descriptor-README.md)
- [bundles-secrets-descriptor-README.md](../../../service/configuration/bundles-secrets-descriptor-README.md)
- [assembly-descriptor-README.md](../../../service/configuration/assembly-descriptor-README.md)

## Concepts

### 1. A runtime is a real workspace, not just a command

When you run KDCube locally, the important thing is the runtime workdir.

That runtime usually contains:

- `config/install-meta.json`
- `config/assembly.yaml`
- `config/bundles.yaml`
- `config/bundles.secrets.yaml`
- other generated runtime files

Once that runtime already exists, `kdcube` normally reuses it.

That means:

- the runtime keeps using the descriptor files already staged under `workdir/config/`
- `kdcube --build --upstream` updates the platform checkout and rebuilds from it
- it does not throw away the runtime descriptor state and start over

So there are two different local use cases:

- reuse the current runtime because you want to keep its config and data
- start a fresh empty runtime because you want to test first-run bootstrap

### 2. The three files do different jobs

`assembly.yaml` is about the runtime topology:

- host paths
- mounted roots
- storage roots
- service-wide runtime config

`bundles.yaml` is about bundle definitions and deployment-scoped non-secret bundle config:

- which bundles exist
- which one is default
- whether a bundle is local-path or git-backed
- bundle props under `config:`

`bundles.secrets.yaml` is about deployment-scoped bundle secrets:

- API tokens
- webhook shared secrets
- MCP shared tokens
- other bundle-scoped credentials

### 3. Local path bundles and git bundles are different workflows

A local path bundle is for editing code directly from your source tree.

A git bundle is for:

- pinned refs
- managed delivery
- versioned deployment

You can move a bundle from one style to the other, but do not mix both styles in one bundle entry.

### 4. Host path and runtime path are not the same thing

This is the main source of confusion.

Example:

- host root: `/Users/you/src`
- runtime root: `/bundles`

If a bundle lives on the host at:

```text
/Users/you/src/my-repo/src/my_bundle
```

then the bundle entry in `bundles.yaml` must use:

```text
/bundles/my-repo/src/my_bundle
```

The host path belongs in `assembly.yaml`.
The runtime-visible path belongs in `bundles.yaml`.

### 5. Managed bundles and unmanaged bundles are separate

Managed bundles are:

- git-resolved bundles
- built-in example bundles materialized by the platform

Unmanaged bundles are:

- local path bundles mounted from your own source tree

Keep those roots separate.

In practice:

- `assembly.yaml -> paths.host_bundles_path` points to your source tree root
- `assembly.yaml -> paths.host_managed_bundles_path` points to the runtime-managed cache

### 6. Descriptor-backed bundle config is operational state

Bundle props and secrets are not the same as code.

Deployment-scoped bundle props live in:

- `bundles.yaml`

Deployment-scoped bundle secrets live in:

- `bundles.secrets.yaml` in local `secrets-file` mode
- or the configured provider authority in other deployments

User-scoped props and secrets are different:

- user props are not stored in `bundles.yaml`
- user secrets are not stored in `bundles.secrets.yaml`

For the exact split, use:

- [bundle-props-secrets-README.md](../bundle-props-secrets-README.md)

## What To Do In Practice

### If you want to reuse the runtime you already have

Use the existing runtime if your goal is:

- test the updated CLI
- test newer platform code
- keep the current descriptor state
- keep the current local runtime data

Typical commands:

```bash
pip install -e /abs/path/to/kdcube_cli
kdcube --workdir ~/.kdcube/kdcube-runtime/my_runtime --build --upstream
```

What this does:

- reuses `workdir/config/install-meta.json`
- reuses `workdir/config/*.yaml`
- pulls the newer upstream repo state
- rebuilds from it
- does not reseed the default descriptors

So if you need to change bundle roots or bundle entries in that runtime, edit the files already under:

```text
<workdir>/config/
```

### If you want to test first-run bootstrap

Do not reuse the existing runtime.

Use a new empty workdir:

```bash
kdcube --workdir ~/.kdcube/kdcube-runtime-test-default
```

That is the flow that exercises:

- default descriptor seeding
- first-run prompt behavior
- local-first runtime bootstrap

### If you want to change the host bundles root

Edit:

```text
<workdir>/config/assembly.yaml
```

Set:

```yaml
paths:
  host_bundles_path: "/Users/you/src"
```

This means:

- the host parent root is `/Users/you/src`
- local path bundles will be mounted under `/bundles/...`

After changing it, rerun:

```bash
kdcube --workdir ~/.kdcube/kdcube-runtime/my_runtime --build --upstream
```

Then verify:

```bash
kdcube --workdir ~/.kdcube/kdcube-runtime/my_runtime --info
```

Check:

- host bundles path
- container bundles root
- host managed bundles path
- container managed bundles root

### If you want to run a bundle directly from your local source tree

Define it as a pure path bundle in:

```text
<workdir>/config/bundles.yaml
```

Recommended form:

```yaml
bundles:
  items:
    - id: "my.bundle@1-0"
      name: "My Bundle"
      path: "/bundles/my-repo/src/my_bundle"
      module: "entrypoint"
```

This is the easiest form to reason about:

- `path` is the actual bundle root in the runtime
- `module` is the module inside that root

If you do this, do not leave:

- `repo`
- `ref`
- `subdir`

on that same bundle entry.

### If you want to switch a bundle from git to local path

Edit `bundles.yaml`.

Remove the git shape:

- `repo`
- `ref`
- `subdir`

Replace it with the local path shape:

- `path`
- `module`

Then rerun:

```bash
kdcube --workdir ~/.kdcube/kdcube-runtime/my_runtime --build --upstream
```

If the code is already mounted locally and only the code changed, not the runtime topology, a bundle reload is usually enough:

```bash
kdcube --workdir ~/.kdcube/kdcube-runtime/my_runtime --bundle-reload my.bundle@1-0
```

Use `--build --upstream` when you changed:

- `assembly.yaml`
- descriptor topology
- platform code
- compose/runtime files

Use `--bundle-reload` when you changed:

- bundle code
- `bundles.yaml`
- `bundles.secrets.yaml`

and the runtime topology itself is still the same.

### If you want to switch a bundle from local path back to git

Edit `bundles.yaml`.

Remove the local path shape:

- `path`

Replace it with the git shape:

- `repo`
- `ref`
- `subdir`
- `module`

Then rebuild or restart the runtime:

```bash
kdcube --workdir ~/.kdcube/kdcube-runtime/my_runtime --build --upstream
```

### If the bundle is still git-backed but should use a different ref

Edit only the git fields in `bundles.yaml`, for example:

- `ref`
- or `repo` if needed

Then rerun:

```bash
kdcube --workdir ~/.kdcube/kdcube-runtime/my_runtime --build --upstream
```

### If you added or changed bundle props

Bundle props are deployment-scoped non-secret config.

Put them into:

```text
<workdir>/config/bundles.yaml
```

Example:

```yaml
bundles:
  items:
    - id: "my.bundle@1-0"
      path: "/bundles/my-repo/src/my_bundle"
      module: "entrypoint"
      config:
        api:
          header_name: "X-My-Bundle-Token"
        features:
          enabled: true
```

Then apply them with:

```bash
kdcube --workdir ~/.kdcube/kdcube-runtime/my_runtime --bundle-reload my.bundle@1-0
```

Use `--build --upstream` instead only if you also changed runtime topology or platform code.

### If you added or changed bundle secrets

Bundle secrets are deployment-scoped secret config.

Put them into:

```text
<workdir>/config/bundles.secrets.yaml
```

Example:

```yaml
bundles:
  items:
    - id: "my.bundle@1-0"
      secrets:
        api:
          shared_token: "replace-me"
```

Then apply them with:

```bash
kdcube --workdir ~/.kdcube/kdcube-runtime/my_runtime --bundle-reload my.bundle@1-0
```

In code, the clean split is:

```python
header_name = self.bundle_prop("api.header_name", "X-My-Bundle-Token")
shared_token = get_secret("b:api.shared_token")
```

### If bundle props or bundle secrets were changed from bundle admin

That is still operational configuration.

In local descriptor-backed mode:

- deployment-scoped bundle prop changes should persist into `bundles.yaml`
- deployment-scoped bundle secret changes should persist into `bundles.secrets.yaml` in `secrets-file` mode

That means the local descriptor files remain the runtime authority and should be treated as real state, not as throwaway examples.

If someone changes those values through bundle admin, do not later overwrite them with stale copies.

### If the bundle writes user props or user secrets

That does not belong in bundle descriptors.

User-scoped writes are normal business/runtime state:

- user props are not exported to `bundles.yaml`
- user secrets are not exported to `bundles.secrets.yaml`

Do not expect bundle reload or descriptor export to reconstruct user-scoped state.

### If you want to know what the runtime is actually using

Run:

```bash
kdcube --workdir ~/.kdcube/kdcube-runtime/my_runtime --info
```

Use this when you need to answer:

- which descriptor files are active
- which repo/workdir this runtime is using
- what the host and container bundle roots are
- where managed bundles live

## The `path` And `module` Question

There are two valid forms, but one is easier to work with.

### Recommended form

Use this when `path` is the actual bundle root:

```yaml
path: /bundles/my-repo/src/my_bundle
module: entrypoint
```

This is the most readable form and should be your default.

### Alternative form

Use this only when `path` is the parent folder that contains the bundle directory:

```yaml
path: /bundles/my-repo/src
module: my_bundle.entrypoint
```

This also works, but it is less direct because the runtime resolves the real bundle root from the module base.

For normal local development, prefer the first form.

## What To Remember

If you only remember the essentials, remember these:

- reuse the current runtime when you want to keep its config and data
- use a fresh workdir only to test first-run bootstrap
- `assembly.yaml` owns the host roots
- `bundles.yaml` owns bundle definitions and non-secret deployment props
- `bundles.secrets.yaml` owns deployment-scoped bundle secrets
- local path bundles should usually use bundle-root `path` plus `module: entrypoint`
- after changing descriptor-backed bundle config, apply it with bundle reload
- after changing runtime topology or platform code, rerun `--build --upstream`
