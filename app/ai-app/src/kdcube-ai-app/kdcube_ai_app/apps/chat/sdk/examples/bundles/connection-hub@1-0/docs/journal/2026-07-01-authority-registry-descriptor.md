---
id: kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/connection-hub@1-0/docs/journal/2026-07-01-authority-registry-descriptor.md
title: "Authority Registry Descriptor"
summary: "Decision note: keep request identity mechanics separate from the canonical authority registry; represent platform authorities with platform: true."
status: active
tags: ["connection-hub", "authority-registry", "platform-authority", "bundle-session", "descriptor"]
---

# Authority Registry Descriptor

Date: 2026-07-01

## Problem

Connection Hub already has `config.identity`, but that branch currently means
request-identity mechanics:

- authenticator selector cache;
- request authenticators;
- role resolver hook;
- link-flow UX.

It is too narrow to become the full authority registry. We also need to support
more than one platform-capable authority, similar to multi-Cognito deployments
and bundle-session deployments.

## Decision

Add a separate canonical branch:

```yaml
authority_registry:
  authorities:
    kdcube.platform:
      label: KDCube platform authority
      platform: true
      providers:
        versatile_telegram_session:
          type: bundle_session_login
          enabled: true
          label: Versatile Telegram platform session
          host:
            bundle_id: versatile@2026-03-31-13-36
            route: public
            operation: auth_telegram_session
          input:
            authenticator_ref:
              authority_id: telegram.kdcube_ref
              provider_id: telegram_bot_init_data
              integration_id: telegram.kdcube_ref
          issuer:
            type: kdcube_session_token
            ttl_seconds: 43200
          grants:
            roles:
              - kdcube:role:chat-user
            permissions:
              - kdcube:*:chat:*;read;write
```

`platform` is a property of an authority:

```yaml
platform: true
```

It is not a separate descriptor kind and not a one-off config branch.

## Bundle-Hosted Provider Rule

A bundle may host the proof exchange and session issuance endpoint, but the
bundle must not own the authority policy.

The provider instance is registered under the target authority:

```yaml
authority_registry:
  authorities:
    kdcube.platform:
      platform: true
      providers:
        versatile_telegram_session:
          type: bundle_session_login
          host:
            bundle_id: versatile@2026-03-31-13-36
            route: public
            operation: auth_telegram_session
          input:
            authenticator_ref:
              authority_id: telegram.kdcube_ref
              provider_id: telegram_bot_init_data
              integration_id: telegram.kdcube_ref
          issuer:
            type: kdcube_session_token
            ttl_seconds: 43200
          grants:
            roles:
              - kdcube:role:chat-user
            permissions:
              - kdcube:*:chat:*;read;write
```

Connection Hub owns:

- authority id;
- platform-ness;
- provider instance id and type;
- allowed roles/permissions;
- TTL;
- host metadata.

The hosting bundle owns:

- provider-specific proof exchange;
- calling the platform bundle-session authority;
- failing closed if the registered provider is missing, disabled, not
  platform-capable, or not hosted by that bundle operation.

## Why This Matters

This keeps roles and permissions defined in one place: the Connection Hub
registry. It also lets us support multiple platform authorities later without
adding incompatible config shapes.

The same registry can describe:

- Cognito-backed platform authorities;
- bundle-session platform authorities;
- custom authority providers loaded from bundles;
- request authenticators and provider instances as the model matures.

## Follow-Up

- Keep adding provider kinds to this registry instead of inventing local bundle
  config branches for authority policy.
- Promote request authenticators/custom authorities into this vocabulary as
  they become first-class provider instances.
- Keep formal docs aligned:
  - `docs/sdk/solutions/connections/connection-hub-solution-README.md`
  - `docs/sdk/solutions/connections/authority-providers/authority-provider-runtime-README.md`
  - `docs/sdk/solutions/connections/storage-model/storage-model-README.md`
  - `versatile@2026-03-31-13-36/docs/integrations/platform-session-issuer.md`

## Implementation Update

Implemented on 2026-07-01:

- `kdcube_ai_app.apps.chat.sdk.solutions.connections.authority_registry_config`
  flattens and resolves `authority_registry.authorities.*.providers.*`.
- `AuthorityRegistryClient` lets hosted providers ask Connection Hub for their
  registered provider instance.
- Connection Hub exposes `authority_provider_resolve` as an operations API.
- Versatile's hosted Telegram session login resolves its platform-session
  authority provider from Connection Hub instead of local bundle policy.
- The custom-authority runtime uses bundle/session auth; the normal demo runtime
  remains Cognito/multi-Cognito and must not be mixed into this test setup.
