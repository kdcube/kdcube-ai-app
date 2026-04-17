# KDCube Builder — Claude Code Plugin

Claude Code plugin for KDCube development: install the CLI, start the runtime, reload and test bundles, build bundle code.

Once installed, just talk to Claude naturally — no slash commands needed:

> "start KDCube"  
> "reload the telegram-bot bundle"  
> "what's running?"

---

## Prerequisites

- [Claude Code](https://claude.ai/code) installed
- Python 3.9+
- Docker (for running KDCube locally)
- A clone of this repository

---

## Install

### 1. Clone the repo

```bash
git clone https://github.com/kdcube/kdcube-ai-app.git
cd kdcube-ai-app
```

### 2. Register the marketplace

```bash
claude plugin marketplace add \
  /abs/path/to/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/builder_plugin
```

You will be prompted to confirm. The marketplace is named `kdcube-builder-marketplace`.

### 3. Install the plugin

```bash
claude plugin install kdcube-builder@kdcube-builder-marketplace --scope user
```

`--scope user` installs globally for your user — available in every project.  
Use `--scope project` to install only for the current directory.

### 4. Install kdcube-cli

Open Claude Code and ask:

```
install kdcube
```

Claude will run `pip install kdcube-cli` (or `pipx install kdcube-cli` if pipx is available) automatically.  
Or do it manually:

```bash
pipx install kdcube-cli
# or
pip install --user kdcube-cli
```

---

## First run

Open Claude Code in your project and say:

```
what's running in kdcube?
```

Claude will check the CLI, descriptor profile, workdir, and Docker containers and report the status.

If descriptors are not configured yet, Claude will ask for the path to your descriptor directory (`assembly.yaml`, `bundles.yaml`, `gateway.yaml`, `secrets.yaml`) and set it up.

---

## Update

Pull the latest changes and reinstall:

```bash
git pull
claude plugin update kdcube-builder@kdcube-builder-marketplace
```

---

## Uninstall

### Remove the plugin

```bash
claude plugin uninstall kdcube-builder@kdcube-builder-marketplace --scope user
```

### Remove the marketplace

```bash
claude plugin marketplace remove kdcube-builder-marketplace
```

---

## Validate (for development)

From the marketplace root:

```bash
claude plugin validate /abs/path/to/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/builder_plugin
```

To run Claude with the plugin loaded directly without installing:

```bash
claude --plugin-dir /abs/path/to/builder_plugin/plugins/kdcube-builder
```

---

## What's inside

```
builder_plugin/
  .claude-plugin/
    marketplace.json
  plugins/
    kdcube-builder/
      .claude-plugin/
        plugin.json
      scripts/
        kdcube_local.py       ← CLI wrapper (install, start, reload, status, ...)
      skills/
        kdcube-dev/           ← natural language orchestrator (main entry point)
        local-runtime/        ← start / reload / stop / bundle-tests
        verify-reload/        ← verify bundle cache eviction after reload
        use-descriptors/      ← point a profile at an existing descriptor directory
        bootstrap-local/      ← generate a fresh local descriptor set
        bundle-builder/       ← bundle authoring with docs and examples
      templates/
        assembly.yaml
        bundles.yaml
        ...
```

## CLI reference

kdcube-cli docs: https://pypi.org/project/kdcube-cli/