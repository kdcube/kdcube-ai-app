# KDCube Builder Plugin — Dev Notes

## Goal

Claude Code plugin that lets Claude operate KDCube: run CLI, reload bundles, test, build.

Steps:
1. Minimal CLI — reload bundle by id, verify it's live
2. Edit bundle code + reload
3. Browser / UI testing

---

## Step 1 status

| Item | Done |
|---|---|
| Plugin scaffold + marketplace manifest | ✓ |
| Skills: bundle-builder, bootstrap-local, local-runtime, use-descriptors | ✓ |
| `kdcube_local.py`: use-descriptors, verify-reload commands | ✓ |
| `skills/verify-reload/SKILL.md` | ✓ |
| `skills/kdcube-dev/SKILL.md` — natural language orchestrator with TRIGGER | ✓ |
| `kdcube_local.py`: status command | ✓ |
| End-to-end smoke test | ✗ |

---

## Session log

**2026-04-17**
- Added `verify-reload` skill — wraps `kdcube_local.py verify-reload <bundle_id>`, checks proc cache eviction
- Added `kdcube-dev` orchestrator skill — no `disable-model-invocation`, has `TRIGGER when:` so Claude auto-invokes on natural language KDCube requests; maps intents (start/reload/test/build/status) to sub-skill chains
- Added `status` subcommand to `kdcube_local.py` — shows kdcube CLI availability, descriptor profile symlink, workdir, running docker containers
- Clarified install flow: `claude plugin marketplace add <path>` + `claude plugin install kdcube-builder@kdcube-builder-marketplace --scope user`

**Next:** smoke test — start runtime, reload telegram-bot, verify via natural language