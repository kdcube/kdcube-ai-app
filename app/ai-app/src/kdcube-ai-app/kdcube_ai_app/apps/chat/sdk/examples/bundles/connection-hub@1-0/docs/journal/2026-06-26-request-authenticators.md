---
id: kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/connection-hub@1-0/docs/journal/2026-06-26-request-authenticators.md
title: "2026-06-26 - Request Authenticators"
summary: "Connection Hub now exposes a request-authenticate operation for gateway/app auth selectors: request proof in, linked authority out."
status: active
tags: ["connection-hub", "authenticators", "telegram", "gateway", "identity-authority"]
---

# 2026-06-26 - Request Authenticators

Connection Hub now owns a provider-neutral request-authentication endpoint:

```text
request_authenticate(request envelope)
  -> select provider family from request shape
  -> verify configured Connection Hub authenticator module row
  -> resolve identity link
  -> resolve platform authority
  -> return identity_authority
```

The platform gateway uses this through the request-auth selector. If Connection
Hub accepts the request, the gateway receives a complete `UserSession` with
effective roles and `identity_authority`. If Connection Hub declines, normal
platform token/cookie auth continues.

The important product decision: provider authenticators are modules inside
Connection Hub. Callers do not import Telegram/Slack/OIDC verification logic.
They pass a normalized request envelope; Connection Hub selects a configured
authenticator module, verifies the proof, resolves an identity link, and returns
authority.

## Endpoint

New public operation:

```text
POST /public/request_authenticate
```

Input is a `RequestEnvelope`:

```json
{
  "method": "POST",
  "path": "/api/...",
  "headers": {"x-telegram-init-data": "..."},
  "query": {},
  "cookies": {}
}
```

KDCube-controlled callers should also send the connection selector:

```json
{
  "headers": {
    "x-telegram-init-data": "...",
    "x-kdcube-auth-provider": "telegram",
    "x-kdcube-auth-integration-id": "telegram.default"
  }
}
```

`integration_id` is a non-secret deployment handle configured on the app
surface. If present, Connection Hub tries the mapped authenticator row only.
Uncontrolled inbound hooks may lack this header and can use the provider-family
fallback.

Output is an `AuthenticatedRequest`:

```json
{
  "ok": true,
  "authenticated": true,
  "provider": "telegram",
  "provider_subject": "100200300",
  "actor_user_id": "telegram_100200300",
  "platform_user_id": "a1b2c3d4-...",
  "identity_authority": {
    "actor_user_id": "telegram_100200300",
    "platform_user_id": "a1b2c3d4-...",
    "economics_user_id": "a1b2c3d4-...",
    "user_type": "privileged",
    "platform_roles": ["kdcube:role:super-admin"]
  }
}
```

## Telegram Authenticators

Telegram supports multiple configured bots. Descriptor-defined rows use the
generic path:

```yaml
identity:
  authenticators:
    - id: telegram.kdcube_ref
      provider: telegram
      authority_id: telegram.kdcube_ref
      where: built-in
      role_providing: false
      secret_ref: identity.authenticators.telegram_kdcube_ref.bot_token
      definition:
        label: KDCube Ref Telegram bot
        bot_name: kdcube-ref
        bot_username: kdcube_doc_bot
        web_app_auth_max_age_seconds: 86400
      enabled: true
```

Controlled requests say both "Telegram initData is present" and which
authority/authenticator should verify it, via `X-KDCube-Auth-Authority-ID` and
`X-KDCube-Auth-Authenticator-ID`. Uncontrolled hooks may only say "Telegram
initData is present", in which case Connection Hub uses the provider fallback
order. Legacy `integration_id`/`connection_id` names are selector aliases only.

`subject_namespace` is optional for Telegram because the provider already
defines the subject domain (`telegram:<id>`). Use `subject_namespace` only for
generic authenticators such as OIDC, webhook, or API-key when the verifier
provider and the subject namespace are not the same thing.

## Storage Boundary

Request-authenticator rows contain metadata only:

```text
authenticator_id, provider, authority_id, connection_id, enabled, role_providing,
subject_namespace, selector, verifier, properties, secret_ref
```

The storage table keeps `connection_id` as a selector alias for older callers.
Public API/UI/config should use `authority_id` and `authenticator_id`.

Widget-managed rows are stored in Postgres:

```text
<schema>.connection_hub_request_authenticators
```

Secret values are not stored in this table. They stay in bundle secrets and are
read with `get_secret("b:<secret_ref>")`. The admin API rejects secret value
fields such as `secret_value`, `bot_token`, `client_secret`, `signing_secret`,
or `api_key`.

See [../storage/README.md](../storage/README.md).

## Security Boundary

- Telegram `initData` proves the Telegram actor only.
- Identity links map `telegram:<id>` to a platform user.
- Platform roles/economics come from the linked platform principal.
- Telegram-local roles must not be converted into platform roles.

The gateway's final object is `UserSession`; downstream app code should not
parse Telegram auth again.
