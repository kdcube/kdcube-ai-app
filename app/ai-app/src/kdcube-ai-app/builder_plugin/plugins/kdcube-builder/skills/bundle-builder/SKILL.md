---
description: Build or repair KDCube bundles. Use the KDCube bundle docs, the versatile reference bundle, and the shared bundle suite before writing code.
---

# KDCube Bundle Builder

Use this skill when the task is bundle authoring: writing a bundle from scratch, wrapping an
existing application into a bundle, or adding features to an existing bundle.

## What one bundle can contain

One KDCube bundle can combine:

- Python backend entrypoint
- authenticated APIs via `@api(route="operations")`
- public APIs via `@api(route="public", public_auth=...)`
- widgets via `@ui_widget(...)`
- a full custom iframe UI via `@ui_main`
- storage
- deploy-scoped props and secrets
- user-scoped props and secrets
- scheduled jobs via `@cron(...)`
- dependency-isolated helpers via `@venv(...)`
- React v2 and/or Claude Code and/or custom agents
- optional Node or TypeScript backend logic behind a Python bridge

## Read order

Check whether `CLAUDE_PLUGIN_OPTION_KDCUBE_REPO_ROOT` is set. If it is, use **local paths**
(faster, no network). Otherwise fall back to the GitHub URLs below.

### Local paths (when repo root is available)

Let `R = $CLAUDE_PLUGIN_OPTION_KDCUBE_REPO_ROOT`. Read in this order with the `Read` tool:

1. `R/app/ai-app/docs/sdk/bundle/bundle-index-README.md`
2. `R/app/ai-app/docs/sdk/bundle/bundle-reference-versatile-README.md`
3. `R/app/ai-app/docs/sdk/bundle/bundle-dev-README.md`
4. `R/app/ai-app/docs/sdk/bundle/bundle-runtime-README.md`
5. `R/app/ai-app/docs/sdk/bundle/bundle-platform-integration-README.md`
6. `R/app/ai-app/docs/sdk/bundle/bundle-props-secrets-README.md`
7. `R/app/ai-app/docs/sdk/bundle/bundle-node-backend-bridge-README.md`

Reference bundle (read all files with `Read` / `Glob`):

- `R/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/versatile@2026-03-31-13-36`

Bundle suite tests (read to understand what the suite validates):

- `R/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/tests/bundle/test_bundle_state.py`
- `R/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/tests/bundle/test_run_bundle_suite.py`

### GitHub fallback (when no local repo)

1. `https://github.com/kdcube/kdcube-ai-app/blob/main/app/ai-app/docs/sdk/bundle/bundle-index-README.md`
2. `https://github.com/kdcube/kdcube-ai-app/blob/main/app/ai-app/docs/sdk/bundle/bundle-reference-versatile-README.md`
3. `https://github.com/kdcube/kdcube-ai-app/blob/main/app/ai-app/docs/sdk/bundle/bundle-dev-README.md`
4. `https://github.com/kdcube/kdcube-ai-app/blob/main/app/ai-app/docs/sdk/bundle/bundle-runtime-README.md`
5. `https://github.com/kdcube/kdcube-ai-app/blob/main/app/ai-app/docs/sdk/bundle/bundle-platform-integration-README.md`
6. `https://github.com/kdcube/kdcube-ai-app/blob/main/app/ai-app/docs/sdk/bundle/bundle-props-secrets-README.md`
7. `https://github.com/kdcube/kdcube-ai-app/blob/main/app/ai-app/docs/sdk/bundle/bundle-node-backend-bridge-README.md`

## Primary examples

Default to `versatile` unless the task is specifically about `ks:` / custom namespace resolvers,
isolated exec, or the Node/TS bridge.

- versatile reference bundle — `versatile@2026-03-31-13-36` (see local path above, or GitHub tree)
- knowledge-space and extended resolver — `kdcube.copilot@2026-04-03-19-05`
- isolated exec — `with-isoruntime@2026-02-16-14-00`
- Node/TS bridge — `resources/node-backend-bridge`

## Bundle placement — CRITICAL

Before creating any bundle, run `/kdcube-builder:kdcube-find-project` to resolve:
- `HOST_BUNDLES_PATH` — the host directory mounted as `/bundles` inside containers
- `BUNDLES_YAML` — `$WORKDIR/config/bundles.yaml`

**Always write the bundle into `HOST_BUNDLES_PATH/<bundle-id>/`.**
Never write bundles into the repo, examples dir, or any other location.
Symlinks do not work across Docker volume mounts — use real directories only.

After creating the bundle, register it in `BUNDLES_YAML` using this exact format:

```yaml
bundles:
  version: "1"
  default_bundle_id: "<bundle-id>"
  items:
    - id: "<bundle-id>"
      name: "<Human Name>"
      path: "/bundles/<bundle-id>"
      module: "entrypoint"
      config:
        role_models:
          gate.simple:
            provider: "anthropic"
            model: "claude-haiku-4-5-20251001"
```

The `path` must use the **container path** (`/bundles/...`), not the host path.

## Workflows

### Write a bundle from scratch

1. Run `/kdcube-builder:kdcube-find-project` to get `HOST_BUNDLES_PATH` and `BUNDLES_YAML`.
2. Read docs (local or GitHub).
3. Read the versatile reference bundle.
4. Create `HOST_BUNDLES_PATH/<bundle-id>/` and write `entrypoint.py` + `__init__.py`.
5. Register the bundle in `BUNDLES_YAML` (see format above).
6. Run bundle tests, then reload.

### Wrap an existing application into a bundle

1. Run `/kdcube-builder:kdcube-find-project`.
2. Read the existing application code to understand its entry points, APIs, and data.
3. Read docs and versatile reference bundle.
4. Map the app's functionality to bundle primitives (`@api`, `@ui_main`, `@cron`, etc.).
5. Write the bundle into `HOST_BUNDLES_PATH/<bundle-id>/` — keep the existing app code untouched, call it from `entrypoint.py`.
6. Register in `BUNDLES_YAML`, run bundle tests, then reload.

### Add a feature to an existing bundle

1. Read the existing `entrypoint.py` and relevant docs section.
2. Make the minimal change that adds the feature.
3. Run bundle tests, then reload.

## Authoring rules

- Read the docs and examples before writing code.
- Do not invent decorators, import paths, or bundle tree layout.
- For third-party Python packages, first check whether the runtime already has them.
- Use `@venv(...)` for dependency-heavy leaf helpers, not for request-bound orchestration.
- Keep communicator, request context, Redis, DB clients, and other live proc/runtime bindings outside `@venv(...)`.
- If a Node backend is needed, keep Python as the bundle boundary and put Node/TS behind a narrow bridge.
- If local runtime setup is needed, use `/kdcube-builder:bootstrap-local` first.

## Validation

Run the shared bundle suite before considering bundle work done:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kdcube_local.py" bundle-tests /abs/path/to/bundle
```

Then reload if the runtime is running:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kdcube_local.py" reload <bundle-id>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kdcube_local.py" verify-reload <bundle-id>
```