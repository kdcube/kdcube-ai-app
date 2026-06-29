---
id: kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/connection-hub@1-0/docs/journal/2026-06-27-telegram-claim-platform-auth.md
title: "2026-06-27 - Telegram Claim Platform Auth"
summary: "The Telegram claim page now owns its KDCube platform sign-in bridge, requires a real platform session before linking, and documents the Cognito client requirements."
status: active
tags: ["connection-hub", "telegram", "platform-auth", "cognito", "identity-links"]
---

# 2026-06-27 - Telegram Claim Platform Auth

## Summary

The Telegram claim URL is a standalone Connection Hub page:

```text
/api/integrations/bundles/<tenant>/<project>/connection-hub@1-0/public/widgets/connections_settings?claim_challenge=<id>
```

It must work even when the host website is not present. Therefore it now uses
KDCube platform frontend config from the runtime itself:

```text
GET /api/cp-frontend-config
  -> auth.oidcConfig
  -> routesPrefix
  -> platform callback URL
```

It does not import the website's `auth.js` and does not depend on
`kdcube.config.json`.

## Bug fixed

The proc app operation path may pass:

```text
user_id = session.user_id or session.fingerprint
```

For anonymous browser sessions that can be a stable anonymous fingerprint. The
claim operation must never treat that as a platform user. Identity-link claim
mutation now requires an authenticated, non-anonymous platform user from the
entrypoint communication context before writing:

```text
telegram:<telegram_user_id> -> platform_user_id
```

If the page is opened while logged out, the claim remains pending and the UI
shows a KDCube sign-in action instead of linking to an anonymous subject.

## Flow

```text
Telegram Mini App
  -> user starts link
  -> Connection Hub creates challenge and returns a claim URL

Browser opens claim URL
  -> widget loads
  -> reads challenge status without claiming
  -> if no authenticated platform user:
       fetch /api/cp-frontend-config
       redirect to <origin><routesPrefix>/callback through OIDC
       carry the claim URL in OIDC state.navigateTo
  -> if an authenticated platform user exists:
       show the Telegram identity and signed-in KDCube user
       wait for explicit user confirmation

KDCube platform callback
  -> creates normal platform browser session/cookies
  -> redirects back to the claim URL when state.navigateTo is an /api target

Claim URL opens again
  -> reads challenge status without claiming
  -> user confirms the link
  -> claim operation sees authenticated platform user and confirmed=true
  -> writes identity link
  -> Telegram Mini App can refresh/show linked state
```

If the browser already has a valid KDCube platform session, the page may skip
login, but it must not write the identity link automatically. It still shows the
current KDCube user and requires an explicit "Link this Telegram account"
action. The claim page also provides `Sign out of KDCube`. This clears the
local browser-side platform session state and platform auth cookies, then
forces the next sign-in attempt to ask for account selection.

## Cognito client configuration

For every KDCube host where this claim flow should work, configure the Cognito
app client used by the platform frontend with:

- OAuth 2.0 authorization-code grant enabled.
- PKCE/public-browser flow enabled; no browser client secret.
- Scopes used by the platform descriptor, normally:
  `openid email profile phone`.
- Callback URL:
  `https://<host><routesPrefix>/callback`

Examples:

```text
https://broodier-maxie-uninferrably.ngrok-free.dev/platform/callback
https://demo.kdcube.tech/platform/callback
https://dev.kdcube.tech/platform/callback
```

If Cognito hosted logout is used elsewhere, also allow a static sign-out URL:

```text
https://<host><routesPrefix>/chat
```

The dynamic claim URL does not need to be registered as a Cognito callback URL.
The OIDC callback is always the platform callback. The claim URL travels inside
OIDC state and is restored by the KDCube callback after sign-in.

Do not register every claim URL as a Cognito logout URL. Logout URLs should be
static, host-level platform routes.

## Favicon

The widget now ships the KDCube platform favicon in its own public assets. This
keeps the standalone claim page branded correctly when it is opened outside the
main website or control-plane shell.

## Boundaries

- Telegram proof still proves only the Telegram actor.
- The claim page proves the KDCube browser/platform actor.
- The link is written only when both proofs are present.
- Platform roles/economics are still resolved from the linked platform
  principal, not from Telegram-local roles.
