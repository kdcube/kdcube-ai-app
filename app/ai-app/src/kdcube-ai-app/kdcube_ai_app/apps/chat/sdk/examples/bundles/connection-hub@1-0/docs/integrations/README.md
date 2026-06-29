---
id: connection-hub@1-0/integrations/README
title: "Connection Hub — Integrations Setup (overview)"
summary: "Common setup shared by every connection-hub provider — the single OAuth callback URL, the hub-level state secret, and the apply/refresh step — plus links to the per-provider setup articles (Google, Slack, iCloud)."
status: "active"
tags: ["integration", "connections", "oauth", "admin", "operator-setup", "prerequisites"]
keywords: ["connection hub setup", "connection_oauth_callback", "oauth_state_secret", "client app", "provider setup"]
see_also:
  - ./google.md
  - ./slack.md
  - ./icloud.md
  - ../../interface/README.md
  - ../../config/bundles.template.yaml
  - ../../config/bundles.secrets.template.yaml
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/integrations/connections-README.md
---

# Connection Hub — Integrations Setup (overview)

The connection-hub **owns** external connections. Before a user can connect an
account, an operator/admin registers the **client app** (the external OAuth
application) for each provider. This is the work that happens **outside** KDCube;
the SDK cannot create Google/Slack apps for you. Each user still connects their
own account afterwards through the **Connections** widget.

Per-provider steps:

| Provider | Mechanism | Article |
| --- | --- | --- |
| Google (Gmail) | OAuth (client app) | [google.md](./google.md) |
| Slack | OAuth (client app) | [slack.md](./slack.md) |
| iCloud | App-specific password (no OAuth) | [icloud.md](./icloud.md) |

Set these once for the commands in the per-provider articles:

```bash
export TENANT="demo-tenant"
export PROJECT="demo-project"
export BUNDLE_ID="connection-hub@1-0"
export PUBLIC_HOST="https://YOUR_PUBLIC_HTTPS_HOST"     # e.g. your ngrok host
```

## The one OAuth callback URL (shared by all providers)

The connections hub uses a **single** redirect URI for every OAuth provider/app:

```bash
echo "$PUBLIC_HOST/api/integrations/bundles/$TENANT/$PROJECT/$BUNDLE_ID/public/connection_oauth_callback"
```

Register this exact URL as an authorized redirect URI on **each** OAuth provider
(Google, Slack). iCloud is not OAuth and needs no redirect URI.

## Hub-level state secret

One secret signs the OAuth `state` for **all** connections providers:

```bash
printf '%s\n' "$(openssl rand -hex 32)"   # → connections.oauth_state_secret
```

```yaml
# bundles.secrets.yaml
secrets:
  connections:
    oauth_state_secret: <RANDOM_HEX>
```

## Client apps are admin data

Each provider can have **multiple client apps** (`connections.providers.<provider>.apps: [...]`),
each with its own `app_id` + `client_id` (config) and `client_secret` (secret).
The Connections widget lets the user pick which app to connect through. The
per-provider articles show the exact keys.

## Apply

After editing `bundles.yaml` / `bundles.secrets.yaml`, **refresh the runtime** so
the bundle reloads and the Connections widget builds. Then open:

```text
$PUBLIC_HOST/api/integrations/bundles/$TENANT/$PROJECT/$BUNDLE_ID/widgets/connections_settings
```

Connected tokens are **user-scoped**, so any other bundle acting for that user
(e.g. `user-automation@1-0` for email delivery) can use them without re-connecting.

Do not commit client secrets, the OAuth state secret, user tokens, or iCloud
app-specific passwords to source control.
