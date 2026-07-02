---
id: kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/connection-hub@1-0/docs/storage/README.md
title: "Connection Hub Storage Map"
summary: "Canonical storage map for connection-hub@1-0: descriptors, bundle secrets, Postgres authenticator metadata, connection-edge state, delegated account state, and runtime caches."
status: active
tags: ["connection-hub", "storage", "secrets", "postgres", "identity", "authenticators", "connections"]
---

# Connection Hub Storage Map

Connection Hub uses several storage surfaces on purpose. Do not collapse them
into one "connection store" concept:

```text
bundles.yaml / descriptor authority
  non-secret deployment config:
    connections providers/apps, identity settings, descriptor-defined authenticators

bundles.secrets.yaml / bundle secrets provider
  deployment secrets:
    OAuth client secrets, Telegram bot tokens, signing secrets

Postgres
  request-authenticator metadata managed by the widget/admin API
    provider, row id, selector/verifier hints, secret_ref

bundle artifact/local state
  current playground connection edges and link challenges
  current delegated-account connection state and user tokens

Redis/cache
  platform runtime caches, props caches, named-service discovery, event delivery
```

The security rule is strict: **Connection Hub metadata may reference a secret,
but must never store the secret value.** Secret values are read through the
bundle secret lifecycle with `get_secret("b:<path>")`.

## Ownership Matrix

| Object | Owner | Storage | Contains secrets? | Notes |
| --- | --- | --- | ---: | --- |
| Provider/app config | operator/admin | `bundles.yaml` effective app props | no | `connections.providers.<provider>.apps[]`, `identity.authenticators[]`, visibility config. |
| OAuth client secret | operator/admin | `bundles.secrets.yaml` or configured bundle secrets provider | yes | `connections.providers.<provider>.apps.<app_id>.client_secret`. |
| Telegram bot token | operator/admin | `bundles.secrets.yaml` or configured bundle secrets provider | yes | Referenced from `identity.authenticators[].secret_ref`, e.g. `identity.authenticators.telegram_kdcube_ref.bot_token`. |
| Request-authenticator row | Connection Hub | Postgres | no | `connection_hub_request_authenticators`; stores metadata and `secret_ref` only. |
| Identity link | Connection Hub | current bundle state | no | Maps `provider + provider_subject -> platform_user_id`. |
| Identity-link challenge | Connection Hub | current bundle state | no | Short-lived challenge/proof state for link flows. |
| Delegated OAuth token | Connection Hub connections framework | user-scoped bundle state | yes, user token | Used by automation to act on a connected external account. |
| iCloud app password | Connection Hub email integration | user-scoped bundle state | yes, user token | iCloud is app-password based; Gmail uses the generic connections provider. |

## Request-Authenticator Metadata

The widget-managed request-authenticator table is provisioned by SDK module
`kdcube_ai_app.apps.chat.sdk.solutions.connections.hub.authenticator_store` in
the tenant/project Postgres schema:

```text
<schema>.connection_hub_request_authenticators
  authenticator_id   text primary key
  tenant             text
  project            text
  bundle_id          text
  provider           text
  authority_id       text
  connection_id      text
  label              text
  enabled            boolean
  role_providing     boolean
  subject_namespace  text
  secret_ref         text
  selector           jsonb
  verifier           jsonb
  properties         jsonb
  created_at         timestamptz
  updated_at         timestamptz
  deleted_at         timestamptz
```

Example row:

```json
{
  "authenticator_id": "telegram.support",
  "provider": "telegram",
  "authority_id": "telegram.support",
  "connection_id": "telegram.support",
  "label": "Support bot",
  "enabled": true,
  "role_providing": false,
  "subject_namespace": "telegram",
  "secret_ref": "identity.authenticators.telegram_support.bot_token",
  "selector": {},
  "verifier": {},
  "properties": {
    "where": "built-in",
    "definition": {
      "bot_username": "support_bot"
    }
  }
}
```

`authority_id` is the identity/grant realm. KDCube-controlled surfaces should
carry `X-KDCube-Auth-Authority-ID` and `X-KDCube-Auth-Authenticator-ID`.
`role_providing` should be
`false` for linked external providers such as Telegram; platform roles come
from the linked platform principal, not from the Telegram-local role.

The corresponding secret value belongs in bundle secrets:

```yaml
bundles:
  items:
    - id: connection-hub@1-0
      secrets:
        identity:
          telegram:
            bot_token_support: "<TELEGRAM_BOT_TOKEN>"
```

`authenticators_upsert` rejects payloads that contain secret value fields such
as `secret_value`, `bot_token`, `client_secret`, `signing_secret`, or `api_key`.
The API accepts only `secret_ref`.

## Descriptor-Defined Authenticators

Operators can also define immutable deployment rows in app config:

```yaml
identity:
  authenticators:
    - id: telegram.kdcube_ref
      provider: telegram
      authority_id: telegram.kdcube_ref
      where: built-in
      enabled: true
      role_providing: false
      secret_ref: identity.authenticators.telegram_kdcube_ref.bot_token
      definition:
        label: KDCube Ref Telegram bot
        bot_name: kdcube-ref
        bot_username: kdcube_doc_bot
        web_app_auth_max_age_seconds: 86400
```

For compatibility, the app also reads:

```yaml
identity:
  telegram:
    authenticators:
      - id: telegram.kdcube_ref
        provider: telegram
        secret_ref: identity.authenticators.telegram_kdcube_ref.bot_token
        enabled: true
```

Runtime rows are the merge of descriptor rows and Postgres rows. When ids
collide, the Postgres row wins for runtime behavior. The UI marks descriptor
rows as `source=config` and Postgres rows as `source=postgres`.

## Connection Edges And Challenges

Identity links are the authority bridge:

```text
verified provider subject
  telegram:100200300
      |
      v
platform user id
  a1b2c3d4-...
```

The current playground implementation keeps connection edges and one-time
challenges in bundle-local state through SDK module
`kdcube_ai_app.apps.chat.sdk.solutions.connections.hub.connection_edges`.
Those records do not contain platform roles. Role/economics authority is
resolved after the link points at a platform principal.

If this app graduates from playground to core identity infrastructure, identity
links and challenges should move to a platform-owned durable store with the same
logical contract. Do not move secret values with them.

## Delegated Accounts

Delegated account connections are separate from connection edges:

```text
platform user id
  -> Gmail/Slack/iCloud account token
```

These tokens let automation act on a user's connected account. They do not prove
platform identity and must not grant platform roles.

The generic connections framework stores OAuth/user token material in user-scoped
bundle state. iCloud app passwords are handled by the email integration and are
also user-scoped state. Deployment OAuth client secrets stay in bundle secrets.

## Runtime Cache

Redis is used by the platform runtime for props cache, named-service discovery,
events, and other ephemeral coordination. It is not the authority for
authenticator secrets, connection edges, or delegated OAuth tokens.

Connection Hub also uses Redis as a short-lived selector cache for
request-authenticator metadata:

```text
identity.authenticator_selector_cache
  enabled: true
  ttl_seconds: 30
```

The cached payload is only the merged authenticator metadata rows used for
candidate selection. It does not cache Telegram proof validation, connection-edge
resolution, platform roles, delegated-account tokens, or authorization results.
`authenticators_upsert`, `authenticators_remove`, and descriptor bootstrap
invalidate the cache.
