---
description: >
  Find the active KDCube workdir, bundle paths, and config files on this machine.
  TRIGGER when: any skill needs HOST_BUNDLES_PATH, bundles.yaml location, workdir, or compose file
  before proceeding. Run this first if the workdir is unknown.
  SKIP: if CLAUDE_PLUGIN_OPTION_KDCUBE_WORKDIR is already set and verified.
disable-model-invocation: true
allowed-tools: Bash, Read
---

# KDCube Find Project

Resolve the active KDCube workdir and key paths. Run this before any operation that needs
to know where bundles live or where config files are.

## Resolution order

Run each step in order and stop at the first match:

```bash
# 1. Check env var set by plugin config
echo $CLAUDE_PLUGIN_OPTION_KDCUBE_WORKDIR

# 2. Check legacy env var
echo $KDCUBE_WORKDIR

# 3. Search for workdir marker upward from current directory
# A valid workdir has config/.env with HOST_BUNDLES_PATH set
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kdcube_local.py" status 2>/dev/null | grep Workdir

# 4. Check the default location
test -f ~/.kdcube/kdcube-runtime/config/.env && echo ~/.kdcube/kdcube-runtime
```

## Once workdir is found, extract key paths

```bash
WORKDIR=<resolved_workdir>

grep "HOST_BUNDLES_PATH\|HOST_GIT_BUNDLES_PATH\|AGENTIC_BUNDLES_ROOT\|COMPOSE_FILE" \
  "$WORKDIR/config/.env"
```

## Report these values before proceeding

| Variable | Meaning |
|---|---|
| `WORKDIR` | Root of the KDCube runtime (config + data) |
| `HOST_BUNDLES_PATH` | Host directory mounted as `/bundles` in containers |
| `BUNDLES_YAML` | `$WORKDIR/config/bundles.yaml` |
| `AGENTIC_BUNDLES_ROOT` | Container path for bundles (usually `/bundles`) |

Use `HOST_BUNDLES_PATH` as the target when creating or copying bundles.
Use `BUNDLES_YAML` when registering a new bundle.