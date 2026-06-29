---
id: connection-hub@1-0/integrations/google
title: "Connection Hub — Google (Gmail) setup"
summary: "Operator step-by-step to create the Google OAuth client the connection-hub uses for Gmail (read + send), the shared connections redirect URI, scopes, refresh tokens, and where the client_id/secret go."
status: "active"
tags: ["integration", "connections", "oauth", "google", "gmail", "operator-setup", "prerequisites"]
keywords: ["google oauth client", "gmail oauth", "gmail api", "connection_oauth_callback", "gmail.send", "access_type offline", "refresh token", "google client_secret"]
see_also:
  - ./README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/integrations/email/email-external-prereq-README.md
---

# Connection Hub — Google (Gmail) setup

Gmail rides the **connections framework** (Google OAuth) — per-connect scopes,
token refresh, and cross-bundle `connection.get_token("google")`. See
[the overview](./README.md) for the shared callback URL and `oauth_state_secret`.

Official refs: Google OAuth for web apps
<https://developers.google.com/identity/protocols/oauth2/web-server> · Gmail API
<https://console.cloud.google.com/apis/library/gmail.googleapis.com>

| # | Where | Action | Output |
| --- | --- | --- | --- |
| 1 | Google Cloud Console | Create or choose a Google Cloud project for this deployment. | Project id |
| 2 | APIs & Services → Library | Enable **Gmail API** in that project. | Gmail API enabled |
| 3 | APIs & Services → OAuth consent screen | Configure the consent screen; while in *Testing*, add each user's Google address under **Test users** (or publish the app). | Users can grant scopes |
| 4 | APIs & Services → Credentials → Create credentials → **OAuth client ID** → **Web application** | Create the client. | **Client ID** + **Client Secret** |
| 5 | The same OAuth client → **Authorized redirect URIs** | Add the shared connections callback (from the overview): `…/connection-hub@1-0/public/connection_oauth_callback` | Redirect registered |
| 6 | `bundles.yaml` | Client ID → the Google client app (below). | config updated |
| 7 | `bundles.secrets.yaml` | Client Secret → the matching secret (below). | secret updated |

**Scopes** (read + send — send is needed for task email delivery):

```text
openid  email  profile
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
```

`bundles.yaml`:

```yaml
config:
  connections:
    providers:
      google:
        apps:
        - app_id: gmail
          label: Gmail
          client_id: <GOOGLE_OAUTH_CLIENT_ID>
          scopes: [openid, email, profile,
                   "https://www.googleapis.com/auth/gmail.readonly",
                   "https://www.googleapis.com/auth/gmail.send"]
          enabled: true
```

`bundles.secrets.yaml`:

```yaml
secrets:
  connections:
    providers:
      google:
        apps:
          gmail:
            client_secret: <GOOGLE_OAUTH_CLIENT_SECRET>
```

## Notes

- **Refresh tokens:** the hub requests `access_type=offline` + `prompt=consent`
  automatically, so Google returns a refresh token and the hub refreshes the
  access token on expiry — required for scheduled task email delivery.
- **Gmail API disabled symptom:** a valid token can still fail Gmail calls if the
  Gmail API is not enabled in the project. Enable it (step 2), wait 1–2 minutes,
  retry.
- You may reuse an existing Google OAuth client (e.g. another bundle's) **as long
  as** you add this bundle's redirect URI (step 5) to it.
