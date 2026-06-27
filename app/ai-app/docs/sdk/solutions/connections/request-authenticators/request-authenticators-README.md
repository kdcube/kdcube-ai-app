---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/request-authenticators/request-authenticators-README.md
title: "Request Authenticators"
summary: "Connection Hub role: verify request proof through provider modules and return linked authority material to the gateway/auth selector."
status: active
tags: ["sdk", "connections", "connection-hub", "authenticators", "request-auth", "gateway"]
updated_at: 2026-06-27
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-hub-solution-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/auth/auth-selector-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/authority-projection/authority-projection-README.md
---
# Request Authenticators

Request authenticators verify proof carried by incoming requests.

```text
Telegram initData
Slack signature
webhook HMAC
API key
OIDC claim
        |
        v
Connection Hub provider module
        |
        v
verified provider identity
```

The gateway does not parse Telegram, Slack, API-key, or webhook proof itself.
It passes a request envelope to Connection Hub and receives an authenticated
result when one provider module accepts it.

## Selector Shape

```text
raw request
   |
   v
RequestAuthSelector
   |
   +-- platform token/cookie/session candidates
   |
   +-- Connection Hub request-auth bridge
         |
         v
       request_authenticate(RequestEnvelope)
         |
         v
       provider module verifies proof
         |
         v
       identity link + authority projection
         |
         v
       AuthenticatedRequest
   |
   v
UserSession
```

Service-level selector behavior is documented in
[Auth Selector](../../../../service/auth/auth-selector-README.md). This document
describes the Connection Hub side of that bridge.

## Request Envelope

The SDK contract passes a JSON-safe view of the request:

```json
{
  "method": "POST",
  "path": "/api/...",
  "url": "https://...",
  "headers": {
    "x-telegram-init-data": "...",
    "x-kdcube-auth-provider": "telegram",
    "x-kdcube-auth-integration-id": "telegram.kdcube_ref"
  },
  "query": {},
  "cookies": {}
}
```

Controlled KDCube surfaces should include:

```http
X-KDCube-Auth-Provider: telegram
X-KDCube-Auth-Integration-ID: telegram.kdcube_ref
```

For third-party callbacks that cannot send custom headers, put the integration
id in the callback URL:

```text
/public/telegram_webhook?integration_id=telegram.kdcube_ref
```

## Integration Id

`integration_id` is a non-secret deployment handle. It says which configured
provider integration this surface is using.

```text
integration_id = telegram.kdcube_ref
  -> Connection Hub authenticator row
  -> provider=telegram
  -> secret_ref=identity.authenticators.telegram_kdcube_ref.bot_token
```

It is not:

- a bot token;
- a Telegram bot id;
- a platform user id;
- an identity link.

If an explicit integration id is present, Connection Hub should try that row
only and fail closed if it is missing or disabled.

## Provider Modules

Provider modules live inside Connection Hub because they need access to:

- Connection Hub authenticator metadata;
- bundle secret references;
- identity-link resolution;
- provider-specific verifier code.

```text
Connection Hub
  provider modules:
    telegram
    slack
    oidc
    api-key
    webhook-hmac
```

Apps and gateway code should not duplicate this verifier logic.

## Output

A successful request-auth bridge returns authority material:

```json
{
  "ok": true,
  "authenticated": true,
  "provider": "telegram",
  "provider_subject": "434804821",
  "actor_user_id": "telegram_434804821",
  "platform_user_id": "02e53484-...",
  "identity_authority": {
    "actor_user_id": "telegram_434804821",
    "platform_user_id": "02e53484-...",
    "economics_user_id": "02e53484-...",
    "user_type": "privileged",
    "platform_roles": ["kdcube:role:super-admin"]
  }
}
```

The gateway turns this into a normal `UserSession`.
