---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/link-flows/channel-first-connection-edge-flow-README.md
title: "Channel-First Connection Edge Flow"
summary: "Connection Hub flow where the user starts inside an external channel that already carries provider auth material, then signs into KDCube to claim that provider proof and write an edge."
status: active
tags: ["sdk", "connections", "connection-hub", "connection-edges", "telegram", "data-bus"]
updated_at: 2026-06-29
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-hub-solution-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-edges/connection-edges-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/widget-auth-context/widget-auth-context-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/request-authenticators/request-authenticators-README.md
---
# Channel-First Connection Edge Flow

Channel-first edge creation starts in a context where external auth material
is already present. Telegram Mini App `initData` is the current implemented
example.

```text
external channel first
  -> prove provider identity
  -> create claim challenge
  -> open KDCube browser claim page
  -> prove platform identity
  -> write connection edge
```

## Current Telegram Roundtrip

```text
1. Telegram App
     provides Telegram.WebApp.initData
          |
          v
2. Versatile Telegram Mini App host
     knows app config:
       authority_id = telegram.kdcube_ref
       authenticator_id = telegram.kdcube_ref.init_data
       Connection Hub widget URL
          |
          v
3. Connection Hub iframe
     receives CONFIG_RESPONSE.authContext.headers:
       X-Telegram-Init-Data
       X-KDCube-Auth-Provider: telegram
       X-KDCube-Auth-Authority-ID: telegram.kdcube_ref
       X-KDCube-Auth-Authenticator-ID: telegram.kdcube_ref.init_data
          |
          v
4. Connection Hub backend
     validates Telegram proof through selected authenticator row
     creates provider-proof claim challenge:
       challenge_id
       provider=telegram
       provider_subject=<telegram_user_id>
       label=<telegram username>
       live_event_session_id=<iframe session>
       status=pending_target_claim
          |
          v
5. Browser claim page
     opens platform_claim_url
     signs into KDCube if needed
          |
          v
6. Connection Hub claim operation
     reads authenticated platform user from KDCube browser session
     computes delegable grants from the platform authority:
       identity:family
       economics:platform-user
       currently held platform roles/permissions
     shows explicit consent even if the browser is already signed in
     writes connection edge:
       telegram.kdcube_ref:<telegram_user_id> -> platform:<platform_user_id>
       grants=<selected delegated grants>
          |
          v
7. Connection Hub Data Bus
     emits connection_hub.edge.changed
     to the original iframe live session
          |
          v
8. Connection Hub iframe
     refreshes edge status and shows the connected Telegram account
```

## Data Sources

| Stage | Data | Source |
| --- | --- | --- |
| Telegram proof | `Telegram.WebApp.initData` | Telegram client runtime |
| Authority/authenticator hints | `telegram.kdcube_ref`, `telegram.kdcube_ref.init_data` | host app server config / bundle props |
| Auth context headers | `X-Telegram-Init-Data`, `X-KDCube-Auth-Authority-ID`, `X-KDCube-Auth-Authenticator-ID` | host `CONFIG_RESPONSE` |
| Verifier secret | Telegram bot token | bundle secrets / secrets service through `secret_ref` |
| Pending challenge | `challenge_id`, provider subject, live event session | Connection Hub backend |
| Platform user | `platform_user_id` | authenticated KDCube browser session |
| Delegable grant inventory | platform roles/permissions plus Connection Hub platform-edge grants | Connection Hub claim operation |
| Selected edge grants | `identity:family`, `economics:platform-user`, selected roles/permissions | browser claim page consent |
| Link update | `connection_hub.edge.changed` | Connection Hub Data Bus |

## Claim Page Login

The claim URL is hosted by Connection Hub:

```text
/api/integrations/bundles/<tenant>/<project>/connection-hub@1-0/public/widgets/connections_settings?claim_challenge=<id>
```

If the browser is not signed into KDCube, the claim page fetches:

```text
GET /api/cp-frontend-config
```

and starts the platform OIDC/Cognito sign-in using the runtime's own platform
frontend config. The website is not required.

```text
claim page
  -> /api/cp-frontend-config
  -> OIDC redirect to Cognito
  -> /platform/callback
  -> redirect back to original claim URL from OIDC state.navigateTo
```

If the browser is already signed in, Connection Hub skips the OIDC roundtrip but
still shows the consent screen. A valid browser session proves platform identity;
it does not automatically grant Telegram every platform capability.

## Consent

The Telegram claim consent writes a real delegation edge. The first two grants
are product/runtime grants owned by Connection Hub:

| Grant | Default | Effect |
| --- | --- | --- |
| `identity:family` | selected | allows features such as Memories to read all runtime user ids connected to the KDCube account |
| `economics:platform-user` | selected | allows economics to evaluate quotas/budgets against the platform user while Telegram stays the actor |

The page may also show platform roles and permissions currently held by the
signed-in KDCube user. Those are not selected by default. If selected, they are
stored as edge grants and can be projected only while the platform user still
holds them.

An edge with no grants is linked but intentionally low-authority. It can prove
the Telegram account belongs to the platform user, but it cannot expand memory
family scope or derive platform roles.

## Why Data Bus Is Used

The browser claim page and the Telegram Mini App iframe are different browser
contexts. The claim succeeds in the browser page, but the Mini App should update
without polling.

```text
iframe starts link
  -> asks for Connection Hub live session
  -> sends live_event_session_id when creating challenge

browser claims link
  -> Connection Hub emits event to stored live_event_session_id

iframe receives event
  -> refreshes status
```

## Security Rules

- Telegram proof never supplies `platform_user_id`.
- The browser claim endpoint must reject anonymous/fingerprint sessions.
- The provider challenge must expire.
- The connection edge is written only after provider proof and platform proof
  meet on the same challenge.
- Telegram-local roles do not become platform roles.
- Existing browser login does not bypass consent.
- Empty-grant edges do not authorize identity-family aggregation.
