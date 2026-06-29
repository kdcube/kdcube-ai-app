---
id: kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/connection-hub@1-0/docs/journal/2026-06-25-identity-links-and-delegated-connections.md
title: "2026-06-25 - Identity Links And Delegated Connections"
summary: "Split Connection Hub into two explicit responsibilities: identity links for resolving platform principals, and connected accounts for delegated automation access."
status: active
tags: ["connection-hub", "identity-links", "delegated-access", "roles", "connections-widget"]
---

# 2026-06-25 - Identity Links And Delegated Connections

## Summary

Connection Hub now treats identity links and delegated account connections as
separate concepts.

```text
external identity proof                    delegated account access
google:user@example.com                    google:gmail OAuth token
telegram:314062490                         slack workspace OAuth token
bundle:some-app:external-user-77           icloud app-specific password
        |                                           |
        v                                           v
platform principal routing                 automation can act for user
```

The split matters because the security question and the automation question are
different:

- "Who is this person in KDCube?" is answered by an identity link.
- "Can automation use this external account?" is answered by a connected account.

## Backend changes

Added a small JSON-backed identity-link store. The implementation now lives in
SDK module `kdcube_ai_app.apps.chat.sdk.solutions.connections.hub.identity_links`.

New authenticated operation aliases:

- `identity_links_list` - list current user's linked external identities;
- `identity_link_upsert` - link a verified external identity to the current
  platform user;
- `identity_link_remove` - unlink one external identity from the current user;
- `identity_link_challenge_create` - create a short-lived one-time proof
  challenge for the current platform user;
- `identity_link_challenge_status` - poll that challenge from the same platform
  user session;
- `identity_resolve` - resolve `provider + provider_subject` into a platform
  principal envelope.

New public operation alias:

- `telegram_identity_link_complete` - validates Telegram Mini App `initData` and
  completes a pending Telegram link challenge.

The resolver response deliberately separates identity resolution from role
resolution:

```json
{
  "ok": true,
  "identity_link": {
    "provider": "google",
    "provider_subject": "user@example.com",
    "platform_user_id": "02e..."
  },
  "principal": {
    "platform_user_id": "02e...",
    "roles": [],
    "permissions": [],
    "role_resolution": {
      "status": "platform_resolver_not_wired",
      "source": "platform.principal_role_resolver"
    }
  }
}
```

The configured role-binding mode exists only as a local development fixture:

```yaml
identity:
  role_resolver:
    mode: configured
  role_bindings:
    "02e...":
      roles:
        - "kdcube:role:admin"
      permissions:
        - "connection-hub:*"
```

The target architecture is that Connection Hub resolves identity and then asks a
platform principal/role resolver for entitlements. The app should not decide
real platform roles itself.

## Widget changes

The existing `connections_settings` widget remains the single user-facing
surface. It is still a React/Redux app, and now has three sections:

- identity links;
- OAuth connection providers such as Gmail/Slack;
- iCloud app-password account settings.

This keeps the user flow in one place while preserving the conceptual split:
identity links for proving/routing a platform user, connected accounts for
delegated automation access.

## Security boundary

The current user-facing link operation only links identities to the current
platform user. It does not let a normal user attach an external identity to a
different platform user or grant roles.

The current manual widget form is a development/onboarding fixture. Production
flows should replace it with provider-specific proof flows: OAuth profile claim,
Telegram login signature, signed app webhook, or another verifier that proves
the external subject before a link is trusted.

Future bundle-auth bridges should perform their own upstream proof first, then
call `identity_resolve`:

```text
incoming request
  -> bundle validates external proof/header/signature
  -> call connection-hub identity_resolve(provider, subject)
  -> receive platform_user_id
  -> platform principal/role resolver supplies roles/permissions
  -> ingress session is created for that platform principal
```

## Telegram link flow

Telegram linking is a two-proof flow. Telegram identity alone is not enough to
create a platform link, because the system also needs to know which KDCube user
is asking to attach that Telegram account.

```text
Connection Hub widget, normal KDCube session
  -> identity_link_challenge_create()
  -> stores challenge_id -> platform_user_id server-side
  -> shows Telegram Mini App URL with link_challenge=<challenge_id>

Versatile Telegram Mini App
  -> receives link_challenge
  -> sends link_challenge + X-Telegram-Init-Data

Connection Hub public endpoint
  -> validates Telegram initData using the bot token
  -> completes challenge if pending and unexpired
  -> writes telegram:<telegram_user_id> -> platform_user_id
```

The Telegram Mini App never sends `platform_user_id`. It only proves the
Telegram side of the link.

If the deployment does not yet configure a Telegram deep-link short name, the
browser widget still shows the `challenge_id`. The user can open the bot menu,
switch to the Mini App's Connect tab, paste the challenge id, and complete the
same proof flow.

## Follow-ups

- Replace configured role bindings with a real platform principal/role resolver.
- Add a trusted/server-side operation path for admin-approved identity links.
- Let OAuth providers attach verified profile subjects automatically after
  connect, with explicit user confirmation.
- Extend the widget with provider-specific proof flows instead of manual
  provider/subject entry.
