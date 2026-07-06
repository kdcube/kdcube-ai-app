---
id: connection-hub@1-0/integrations/google
title: "Connection Hub — Google (Gmail) setup"
summary: "Operator step-by-step to create the Google OAuth connector app the connection-hub uses for Gmail (read + send), the delegated to KDCube redirect URI, scopes, refresh tokens, and where the client_id/secret go."
status: "active"
tags: ["integration", "connections", "oauth", "google", "gmail", "operator-setup", "prerequisites"]
keywords: ["google oauth client", "gmail oauth", "gmail api", "delegated_to_kdcube_oauth_callback", "gmail.send", "access_type offline", "refresh token", "google client_secret"]
see_also:
  - ./README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/integrations/email/email-external-prereq-README.md
---

# Connection Hub — Google (Gmail) setup

Gmail rides the **delegated to KDCube framework** (Google OAuth) —
per-connect claims, token refresh, and brokered credential resolution for
code acting on behalf of the current user. See [the overview](./README.md) for
the delegated to KDCube callback URL and state secret.

This may use the same Google OAuth client as bundle-hosted Google platform
login. If the same client is reused, configure both Google console surfaces:
**Authorized redirect URIs** for the Gmail OAuth callback and **Authorized
JavaScript origins** for the platform-login page. KDCube still treats these as
separate responsibilities in descriptors: platform login verifies Google ID
tokens by client id, while Gmail connected accounts exchange OAuth codes with
client id + client secret.

Official refs: Google OAuth for web apps
<https://developers.google.com/identity/protocols/oauth2/web-server> · Gmail API
<https://console.cloud.google.com/apis/library/gmail.googleapis.com>

| # | Where | Action | Output |
| --- | --- | --- | --- |
| 1 | Google Cloud Console | Create or choose a Google Cloud project for this deployment. | Project id |
| 2 | APIs & Services → Library | Enable **Gmail API** in that project. | Gmail API enabled |
| 3 | APIs & Services → OAuth consent screen | Configure the consent screen; while in *Testing*, add each user's Google address under **Test users** (or publish the app). | Users can grant scopes |
| 4 | APIs & Services → Credentials → Create credentials → **OAuth client ID** → **Web application** | Create the client. | **Client ID** + **Client Secret** |
| 5 | The same OAuth client → **Authorized redirect URIs** | Add every delegated to KDCube callback URL for the runtimes that will use this client. The path ends with `…/connection-hub@1-0/public/delegated_to_kdcube_oauth_callback`. | Redirects registered |
| 6 | `bundles.yaml` | Client ID → the Google connector app (below). | config updated |
| 7 | `bundles.secrets.yaml` | Client Secret → the matching secret (below). | secret updated |

**Scopes** (read + send — send is needed for task email delivery):

```text
openid  email  profile
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
```

## Current Redirect URIs

Add these URL shapes to **Authorized redirect URIs** when the same Google OAuth
client serves local, custom-authority, demo, and dev/staging runtimes. Replace
`<LOCAL_PUBLIC_HOST>` with the current HTTPS tunnel or local public host:

```text
https://<LOCAL_PUBLIC_HOST>/api/integrations/bundles/demo-tenant/demo-project/connection-hub@1-0/public/delegated_to_kdcube_oauth_callback
https://<LOCAL_PUBLIC_HOST>/api/integrations/bundles/demo-tenant/custom-authority/connection-hub@1-0/public/delegated_to_kdcube_oauth_callback
https://demo.kdcube.tech/api/integrations/bundles/demo/demo/connection-hub@1-0/public/delegated_to_kdcube_oauth_callback
https://dev.kdcube.tech/api/integrations/bundles/demo/demo-march/connection-hub@1-0/public/delegated_to_kdcube_oauth_callback
```

If the same Google OAuth client is also used for bundle-hosted platform login,
add these under **Authorized JavaScript origins** too:

```text
https://<LOCAL_PUBLIC_HOST>
https://demo.kdcube.tech
https://dev.kdcube.tech
```

Origins are scheme + host only. Redirect URIs are full callback URLs.

`bundles.yaml`:

```yaml
config:
  connections:
    delegated_to_kdcube:
      enabled: true
      providers:
        google:
          label: Google
          adapter: google.oauth
          enabled: true
          claims:
            gmail:read:
              label: Read Gmail
              provider_scopes: [openid, email, profile,
                                "https://www.googleapis.com/auth/gmail.readonly"]
            gmail:send:
              label: Send Gmail
              provider_scopes: [openid, email, profile,
                                "https://www.googleapis.com/auth/gmail.send"]
          connector_apps:
            gmail:
              label: Gmail
              client_id: <GOOGLE_OAUTH_CLIENT_ID>
              client_secret_ref: connections.delegated_to_kdcube.providers.google.connector_apps.gmail.client_secret
              allowed_claims: [gmail:read, gmail:send]
              enabled: true
```

`bundles.secrets.yaml`:

```yaml
secrets:
  connections:
    delegated_to_kdcube:
      providers:
        google:
          connector_apps:
            gmail:
              client_secret: <GOOGLE_OAUTH_CLIENT_SECRET>
```

## Notes

- **Refresh tokens:** the hub requests `access_type=offline` + `prompt=consent`
  automatically, so Google can return a refresh token. Runtime tools should use
  the brokered credential and surface provider errors clearly if the stored
  access token is no longer usable.
- **Gmail API disabled symptom:** a valid token can still fail Gmail calls if the
  Gmail API is not enabled in the project. Enable it (step 2), wait 1–2 minutes,
  retry.
- You may reuse an existing Google OAuth client (e.g. another bundle's) **as long
  as** you add this bundle's redirect URI (step 5) to it.
