# Claude Code × KDCube Plugin — Status

---

## Goal

Integrate KDCube bundle building with Claude Code so Claude can:
1. Run KDCube via CLI (reload bundle by id, verify it's live)
2. Modify bundle code and reload
3. Communicate with browser to test bundle UI

Steps are additive — each step builds on the previous one.

---

## Plan

### Step 1 · Minimal CLI plugin
- Descriptors are already in the workspace
- Claude can run KDCube CLI, reload a bundle by id, verify it's live

### Step 2 · Modify bundle code + reload
- Claude edits local bundle code (starting with telegram-bot)
- Reloads and verifies after each change

### Step 3 · Browser / UI testing
- Claude opens the UI and tests the bundle end-to-end

---

## Key Files

```
builder_plugin/
  .claude-plugin/marketplace.json       ← marketplace entry
  plugins/kdcube-builder/
    .claude-plugin/plugin.json          ← plugin manifest + userConfig
    scripts/kdcube_local.py             ← core CLI helper (all commands here)
    skills/
      bundle-builder/SKILL.md           ← bundle authoring
      bootstrap-local/SKILL.md          ← generate fresh local descriptors
      local-runtime/SKILL.md            ← start / reload / stop / bundle-tests
      use-descriptors/SKILL.md          ← point profile at existing descriptors
      verify-reload/SKILL.md            ← verify bundle cache eviction
      kdcube-dev/SKILL.md               ← natural language orchestrator (main entry)

app/ai-app/deployment/                  ← real local descriptor set
  assembly.yaml
  bundles.yaml
  bundles.secrets.yaml
  gateway.yaml
  secrets.yaml
```

---

## Session Log

---

### 2026-04-17 · Session 1 — Plugin scaffold + CLI foundation

**Context recovered from git history (commit `041b955f`):**

Plugin structure was already created before this session:
- Marketplace manifest and plugin manifest with `userConfig` (`kdcube_repo_root`, `kdcube_workdir`)
- Four skills: `bundle-builder`, `bootstrap-local`, `local-runtime`, `use-descriptors`

**Work done before this session (staged on branch `feat/claude-kdcube-cli-plugin`):**

`kdcube_local.py` extended with:
- `_docker_container_name(match)` — finds running container by name via `docker ps`
- `cmd_use_descriptors` — creates symlink `~/.kdcube/builder-plugin/profiles/<profile>/descriptors → <dir>`, validates required YAMLs
- `cmd_verify_reload` — POSTs to `http://127.0.0.1:8020/internal/bundles/reset-env` inside proc container, validates JSON response (bundle_id, eviction, count)
- CLI subcommands `use-descriptors` and `verify-reload` wired into argparse
- Fix: removed `bundles.secrets.yaml` from required-files check in `_ensure_descriptors_exist`

Deployment descriptors (`app/ai-app/deployment/`) filled with real values:
- `assembly.yaml` — KDCube company, Cognito auth, S3 storage, local host paths
- `bundles.yaml` — react, eco, kdcube.copilot, with-isoruntime, **telegram-bot** (test bundle for Step 1/2)
- `gateway.yaml` — `processes_per_instance` bumped to 2
- `secrets.yaml` — real API keys

---

### 2026-04-17 · Session 2 — Skills completed, natural language entry point added

**What was missing at start of session:**
- `verify-reload` had a working script command but no `SKILL.md`
- No way for user to just talk to Claude naturally — had to type `/` commands explicitly

**What was done:**

`skills/verify-reload/SKILL.md` — created.
Wraps `kdcube_local.py verify-reload <bundle_id>`. `disable-model-invocation: true`, Claude just runs the command and prints output. Includes three operational rules: when to call it, what to do on error, what `eviction: None` means.

`skills/kdcube-dev/SKILL.md` — created.
Natural language orchestrator. No `disable-model-invocation`, so Claude loads the instructions and reasons. Has `TRIGGER when:` in the description so Claude auto-invokes it when the user mentions KDCube work without typing a slash command. Maps user intents to sub-skill chains:
- "запусти / start" → `local-runtime start latest-image`
- "перезагрузи / reload `<bundle>`" → `local-runtime reload` + `verify-reload` (automatic chain)
- "протестируй / test bundle" → `local-runtime bundle-tests` or `verify-reload`
- "настрой / setup / first time" → ask for descriptors path → `use-descriptors` → offer start
- "что запущено / status" → `kdcube_local.py status` (subcommand still missing — see below)
- "создай бандл / build bundle" → `bundle-builder`

**Key insight:** `kdcube-dev` is only an instruction layer — all actual work still goes through the same `kdcube_local.py` commands via the lower-level skills. User never needs to type `/`.

**Still missing for Step 1 to be complete:**
- `status` subcommand in `kdcube_local.py` — referenced in `use-descriptors` output and `kdcube-dev`, not yet implemented
- End-to-end smoke test: natural language → `use-descriptors` → `start latest-image` → `reload telegram-bot` → `verify-reload telegram-bot`