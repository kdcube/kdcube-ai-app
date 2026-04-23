---
id: ks:docs/next/secrets/secrets-module.md
title: "Draft: Secrets Module"
summary: "Draft design for a dedicated runtime secrets module that replaces env-file secrets with keyed runtime fetches across local and production environments."
draft: true
status: proposal
tags: ["next", "secrets", "design", "runtime", "local", "production"]
keywords: ["runtime secrets module", "replace env secrets", "local secret fetch", "persistent secret storage", "production secret provider", "secret retrieval at runtime"]
see_also:
  - ks:docs/next/secrets/secrets-storage.md
  - ks:docs/configuration/runtime-configuration-and-secrets-store-README.md
  - ks:docs/service/secrets/secrets-service-README.md
---
# Secrets module (draft)

Date: 2026-03-07

## Problem
We currently pass secrets through env files or docker env. This is weak because:
- Any process with host or container access can read env.
- Local installs on multi‑user machines are exposed.
- Docker-compose offers no secure secret store by default.

We need a mechanism that:
- Works for local dev (docker-compose and host runs).
- Works for Kubernetes / production.
- Preserves secrets across restarts.
- Allows services to fetch secrets by key at runtime.
- Avoids leaking secrets into env files or build artifacts.

## Design goals
- Key-value model (similar to GitHub Actions: vars + secrets).
- Two classes of data:
  - Values (non-secret) – config.yaml
  - Secrets (secret) – secret store
- A single interface for all services: `SecretsProvider`.
- Can be bootstrapped without any services already running.

## High-level approach
Introduce a local “Secrets Module” with two modes:
1) **Local node store** (dev / single node)
2) **Cluster store** (k8s / multi-node)

Both expose the same API but differ in how secrets are stored and served.

### 1) Local node store (dev / docker-compose)
- A small local daemon (or library + file store) persists encrypted secrets.
- Secrets are stored at a fixed path under the chosen workdir:
  - `~/.kdcube/kdcube-runtime/secrets/`
- Access is by a Unix domain socket (recommended) or local named pipe on Windows.
- Only the service user can connect to the socket (filesystem permissions).

### 2) Cluster store (k8s / multi-node)
Two options:
- **Kubernetes Secrets** (simple): store secrets as k8s secrets; mount into pods.
- **Vault / external** (stronger): use Vault / cloud secret manager.

In k8s, the same `SecretsProvider` can read from:
- Mounted secret files
- External API (Vault / AWS / GCP)

## API surface
```text
SecretsProvider
  get(key: str) -> str | None
  get_json(key: str) -> dict | None
  list(prefix: str = "") -> list[str]
```

Services should not read env directly for secrets. Instead they call provider.

## Bootstrap flow (when nothing is running)
The installer (CLI) performs bootstrap:
1) Ask user for secrets (interactive).
2) Write secrets into the secret store using `secretsctl`.
3) Store *only* a pointer / handle in config:
   - `SECRETS_PROVIDER=local` or `SECRETS_PROVIDER=k8s`
   - `SECRETS_SOCKET_PATH=/.../secrets.sock`
4) Create a **non-secret** config file that points to the store.

Result:
- Services only know where the provider is, not the secret values.

## Persistence model
Local dev:
- Secrets are stored in an encrypted file under workdir:
  - `~/.kdcube/kdcube-runtime/secrets/store.enc`
- A local key is generated at first run and stored in OS keychain:
  - macOS Keychain
  - Windows Credential Manager
  - Linux libsecret / GNOME keyring

When containers restart:
- The secrets daemon re-opens the encrypted store.
- Services fetch by socket on startup.

## How services get secrets
Two mechanisms:
1) **IPC via Unix socket** (preferred)
   - Only local processes with proper permissions can connect.
   - Socket path mounted into containers (read-only).
2) **Sidecar service** in Docker/K8s
   - The secrets service is a minimal HTTP/gRPC service.
   - Exposes only `get(key)` with strict auth.

## Auth / access control
Local dev:
- Socket permissions + OS user account.
- Optional token handshake stored in memory (not on disk).

Cluster:
- ServiceAccount tokens / mTLS for each service.
- Secrets service enforces policy based on service identity.

## Minimal secrets sidecar protocol (draft)
Local (docker-compose):
- Transport: Unix socket
- Auth: peer credentials + admin token for set + per-service read token

Endpoints:
- `POST /bootstrap`
  - Input: `admin_token`
  - Action: enables `set` for one session
- `POST /set`
  - Input: `key`, `value`
  - Allowed only with `X-KDCUBE-ADMIN-TOKEN`
- `GET /secret/{key}`
  - Allowed only for trusted services (peer-cred UID/GID allowlist) and
    `X-KDCUBE-SECRET-TOKEN`

Cluster (k8s):
- Transport: mTLS
- Auth: service identity via cert (SPIFFE) or service account token

Endpoints are the same, auth changes.

## Storage schema
Key-value pairs. Examples:
```
# values.yaml
TENANT: demo-tenant
PROJECT: demo-project
REDIS_URL: redis://redis:6379/0

# secrets
OPENAI_API_KEY: ...
ANTHROPIC_API_KEY: ...
DB_PASSWORD: ...
```

## Migration path
Phase 1 (now):
- Add `SecretsProvider` interface.
- Default provider reads env (current behavior).

Phase 2 (dev):
- Add local secrets daemon + CLI.
- CLI writes secrets to store and config points to socket.

Phase 3 (prod):
- Implement k8s provider and/or Vault provider.

## Open questions
- Should secrets be per-workdir or global per-user?
- Do we need secret rotation and re-encryption?
- How do we export secrets for CI/CD without exposing them in files? (see section below)

## Threat model and limitations (local IPC)
Important: a Unix socket does **not** protect secrets from malicious processes
that run under the same OS user. If an untrusted process runs as the same UID,
it can connect to the socket and read secrets.

Mitigations (local dev):
- Run KDCube services under a **dedicated OS user** (not your normal shell user).
- Keep socket under a 0700 directory owned by that user.
- Validate caller identity using `SO_PEERCRED` (Linux) / `getpeereid` (macOS)
  and allowlist UIDs/GIDs.
- Require a short-lived in-memory token per service (provided at launch) in
  addition to peer-credential checks.
- Use OS MAC controls (AppArmor / SELinux) to restrict socket access.

Reality check: if the attacker can run code as the same user, you cannot
fully protect secrets on a local machine. The best you can do is reduce the
attack surface and require extra proof of identity.

This is why production should rely on a real secrets backend (Vault / KMS / k8s).

## CI/CD secrets without files
CI/CD should not write secrets to files at rest. Preferred options:
- Use the CI provider’s secrets store (GitHub Actions / GitLab / etc.).
- Use OIDC to exchange short-lived tokens with a cloud secrets manager.
- Mount secrets as in-memory files only at runtime (Kubernetes secrets / Vault).

For local docker-compose (dev only):
- Postgres/Redis credentials are not high-value secrets; allow them in env.
- Application secrets should come from the local secrets store, not env files.

## Sidecar hardening steps (local dev)
Low effort:
- Do not expose secrets service ports to the host.
- Do not write LLM keys to `.env` files.
- Use in‑memory tmpfs for the secrets store.

Medium effort:
- Require `GET /secret/{key}` to include a per‑service token.
- Disable list/get utility functions for humans (CLI only uses `set`).
- Keep secrets sidecar on a separate **internal** network only.
- Add token TTL and max‑uses to reduce long‑lived reuse.

## Sidecar limits (explicit)
- Docker network isolation does **not** protect secrets from host users with
  Docker access. If a process can run `docker exec` or attach a container to
  the network, it can read secrets.
- Same‑user malware can still inspect process memory or intercept tokens.
- This is best‑effort local security, not a strong isolation boundary.

## Local isolation tiers (short)
Tier 0: Same user + env files (weak).
Tier 1: Local secrets store + Unix socket (better, still same‑user risk).
Tier 2: Dedicated OS user (good isolation from your login user).
Tier 3: VM or separate machine (strongest practical local boundary).

## VM mode (how secrets enter the VM)
Option A — **Installer runs inside VM** (cleanest):
- CLI creates VM, then runs `kdcube` inside VM via SSH.
- Secrets are entered inside the VM and never touch host disk.
- Secrets are stored inside the VM (local store / keychain).

Option B — **Host installer streams secrets into VM**:
- CLI prompts on host and streams secrets directly to a secrets daemon in VM.
- No host file writes; secrets travel over an SSH tunnel.
- If the host is compromised during entry, secrets are exposed (inevitable).
