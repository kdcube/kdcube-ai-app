---
id: kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/connection-hub@1-0/docs/journal/2026-06-28-explicit-telegram-claim-confirmation.md
title: "2026-06-28 - Explicit Telegram Claim Confirmation"
summary: "Telegram-first browser claim pages now preview the pending identity proof and require an explicit user confirmation before writing the identity link."
status: active
tags: ["connection-hub", "telegram", "identity-links", "claim-flow", "ux", "security"]
---

# 2026-06-28 - Explicit Telegram Claim Confirmation

## Decision

A valid KDCube browser session is allowed to satisfy the platform-auth side of
the Telegram-first link flow. The page must still never consume the challenge or
write the identity link on load.

The browser claim page now separates the flow:

```text
open claim URL
  -> identity_link_challenge_status
  -> show Telegram identity + current KDCube user
  -> user confirms
  -> identity_link_challenge_claim(confirmed=true)
  -> write telegram:<id> -> platform_user_id
```

If the browser is signed into the wrong KDCube account, the page shows `Sign out
of KDCube` before the claim is written.

## API Contract

`identity_link_challenge_status` is read-only. For provider-first pending
challenges, it may return the Telegram identity preview to the currently
authenticated platform user even though the challenge has no platform owner yet.

`identity_link_challenge_claim` now rejects calls unless the payload includes
`confirmed=true`. This is a backend guard against accidental silent claims by
old or incorrect clients.

## User Impact

The user can still avoid a redundant login when the browser already has a valid
KDCube platform session. The important confirmation step is visible and
intentional: "Link this Telegram account" is the only action that writes the
identity link.
