---
description: >
  Direct kdcube CLI operations — configure a bundle, start/stop the stack, reload.
  TRIGGER when: user wants to add/configure a bundle, init/start/stop KDCube, or reload
  a bundle via CLI.
  SKIP: bundle authoring (use kdcube-dev).
allowed-tools: Bash, Read, Write
---

# KDCube CLI

Direct wrapper around the `kdcube` CLI.

## Basic commands

```bash
kdcube init                  # first-run wizard, creates default workdir; or pass --descriptors-location <dir> for reproducible init
kdcube start                 # launch stack
kdcube stop                  # stop stack
kdcube reload <bundle_id>    # apply staged bundle changes (config/secrets/source patches) without full restart
```

When to use:
- `init` — only on fresh setup, or to re-stage descriptors. Not for daily work.
- `start` / `stop` — bring the stack up/down. One stack per machine at a time.
- `reload <bundle_id>` — after any `kdcube bundle ...` change, or after editing the
  bundle's code/config on disk. Does NOT restart containers.

## Configure a bundle

Add a bundle (local path or git), then `reload`:

```bash
# Local path (container-visible path under /bundles/)
kdcube bundle <bundle_id> --local-path /bundles/my.bundle

# Git repo
kdcube bundle <bundle_id> \
  --git-repo git@github.com:org/my-bundle.git \
  --git-ref <ref>

kdcube reload <bundle_id>
```

## Everything else — read the docs

For anything not covered above (identity flags, config/secrets patch, monorepo subdir,
delete, host-path vs container-path, init source selectors, defaults, export, info,
clean, secrets injection, edge cases, full flag list) — read:

- `repo:kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_cli/README.md`
- `repo:kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_cli/additional_README.md`