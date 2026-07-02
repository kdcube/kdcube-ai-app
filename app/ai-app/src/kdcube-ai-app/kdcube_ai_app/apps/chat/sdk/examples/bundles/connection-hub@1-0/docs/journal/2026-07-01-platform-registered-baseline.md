# Platform Registered Baseline

Date: 2026-07-01
Author: Codex

## Decision

Any configured platform authority that successfully authenticates a user but
returns no roles must be normalized to the baseline platform role:

```text
kdcube:role:registered
```

This rule is centralized in platform auth, not in Cognito, SimpleIDP, or a
specific bundle-session provider.

## Why

A blank role list from a platform authority means "authenticated platform user
with no elevated groups", not "external channel actor". If this normalization is
left to each provider, Cognito, SimpleIDP, bundle-session auth, and future
platform authorities drift into different meanings for the same condition.

## Boundary

This rule applies only after platform authentication succeeds.

It must not be applied to raw external channel proofs such as Telegram initData
or webhook signatures. Those remain external until Connection Hub resolves or
projects them into a platform authority/session.

## Implementation Anchor

- `kdcube_ai_app.auth.AuthManager.REGISTERED_ROLE`
- `kdcube_ai_app.auth.AuthManager.ensure_platform_registered_role`
- direct platform auth boundaries in request auth, gateway, ingress session
  upgrade, accounting socket auth, and delegated credential OAuth browser auth
