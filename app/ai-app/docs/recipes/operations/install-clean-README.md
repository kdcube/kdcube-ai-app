---
id: repo:kdcube-ai-app/app/ai-app/docs/recipes/operations/install-clean-README.md
title: "Install KDCube: Clean Bootstrap"
summary: "Stand up a fresh KDCube runtime with one init: the configured base complectation, the first-run checklist, start, and honest verification."
status: active
tags: ["operations", "install", "bootstrap", "cli", "kdcube-cli"]
updated_at: 2026-07-07
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/recipes/operations/operate-runtime-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/recipes/operations/install-from-descriptors-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/cicd/cli-README.md
---
# Install KDCube: Clean Bootstrap

One init on a fresh machine produces a working ecosystem, ready to change
afterwards. This recipe is the zero-input path; when you have a descriptor
set from an existing environment (the CI/CD path), use
[Install From Descriptors](install-from-descriptors-README.md) instead.

## Prerequisites

- Docker running (`docker version`), ~20 GB free disk (`df -h $HOME`)
- Python 3.11+ (`python3 --version`), `git`
- The first `--build` is slow (node, playwright/chromium, pip image layers);
  later refreshes are cached and fast.

## Install the CLI

```shell
export REPO="$HOME/src/kdcube-ai-app"          # your platform checkout
git clone https://github.com/kdcube/kdcube-ai-app.git "$REPO" 2>/dev/null || true
export CLI_VENV="$REPO/app/venvs/ai-app/kdcube-cli"
export KDCUBE="$CLI_VENV/bin/kdcube"

python3 -m venv "$CLI_VENV"
"$CLI_VENV/bin/pip" install --upgrade pip setuptools wheel
"$CLI_VENV/bin/pip" install -e "$REPO/app/ai-app/src/kdcube-ai-app/kdcube_cli"
"$KDCUBE" --help
```

Reinstall only when the CLI source itself changed — not for ordinary
platform pulls.

## Init

```shell
export TENANT="acme"
export PROJECT="main"

# Optional inputs the init substitutes into the staged defaults:
export KDCUBE_PUBLIC_HOST="kdcube.example.com"   # OAuth redirects, webhooks
export KDCUBE_ADMIN_EMAIL="admin@example.com"    # bootstrapped as super-admin

"$KDCUBE" init --path "$REPO" --tenant "$TENANT" --project "$PROJECT" --build \
  --set-secret services.openai.api_key "$OPENAI_API_KEY" \
  --set-secret services.anthropic.api_key "$ANTHROPIC_API_KEY"
```

`init` is first-time creation ONLY: it refuses an already-initialized
workdir. `init --build` builds images and stops — nothing runs until
`kdcube start`.

### What the init stages

The base complectation, already configured (a pure config overlay — the
apps ship in the image and auto-discover):

```text
connection-hub@1-0          identity, consent, delegated credentials, OAuth
kdcube-services@1-0         managed MCP surfaces + named-services bridge
user-memories@2026-06-26    the mem provider + memories widget
workspace@2026-03-31-13-36  showcase scene + chat wired to everything
```

Default identity is the bundle-session flavor: Google sign-in validated by
the workspace app, KDCube session issued by Connection Hub — no external
IdP. `KDCUBE_ADMIN_EMAIL` becomes the super-admin bootstrap rule.

### The first-run checklist

Init ends by printing the placeholders still unfilled (`<FILL_ME>` secret
slots; `<PUBLIC_HOST>` / `<ADMIN_EMAIL>` when their env vars were unset).
Features backed by an unfilled slot stay inactive; everything else runs.
Fill slots later in `$WORKDIR/config/bundles.yaml` /
`bundles.secrets.yaml` — every slot carries a comment saying what it is and
where to get it — or via the AI Bundles dashboard.

## Start and verify

```shell
export WORKDIR="$HOME/.kdcube/kdcube-runtime/${TENANT}__${PROJECT}"
"$KDCUBE" defaults --default-tenant "$TENANT" --default-project "$PROJECT" --default-workdir "$WORKDIR"
"$KDCUBE" start
```

`start` creates and starts the containers, runs the one-shot postgres-setup
schema bootstrap, and preloads bundles (materializing git-backed ones and
building widget UIs). First start takes a minute or two.

Verify in three layers — `kdcube info` is necessary but NOT sufficient (it
reports process/mount state, not per-bundle build outcomes):

```shell
"$KDCUBE" info

# 1) the UI actually answers — the real done-signal:
curl -s -o /dev/null -w "chat UI -> HTTP %{http_code}\n" http://localhost:5173/platform/chat  # want 200

# 2) staged descriptors are the runtime authority:
ls "$WORKDIR/config/"

# 3) per-bundle build outcomes live in the proc logs:
PROC="$(docker ps --format '{{.Names}}' | grep chat-proc | head -1)"
docker logs --since 10m "$PROC" 2>&1 | grep -iE "bundle.ui|widget:.*build (done|failed)|preload|ERROR|Traceback" | tail -40
```

You want to SEE `widget:... build done` per UI bundle and NOT see
`build failed` / `Traceback`.

## After install

Daily lifecycle, config changes, platform updates, export/import:
[Operate A KDCube Runtime](operate-runtime-README.md).
