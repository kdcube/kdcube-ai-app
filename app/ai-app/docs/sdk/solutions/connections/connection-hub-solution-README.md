---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-hub-solution-README.md
title: "Connection Hub Solution"
summary: "Canonical map of Connection Hub roles: identity links, request authenticators, authority projection, delegated accounts, link flows, and widget auth-context transport."
status: active
tags: ["sdk", "solutions", "connections", "connection-hub", "identity", "auth", "authority", "delegated-accounts"]
updated_at: 2026-06-27
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/identity-links/identity-links-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/link-flows/channel-first-identity-linking-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/link-flows/platform-first-identity-linking-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/request-authenticators/request-authenticators-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/authority-projection/authority-projection-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/delegated-accounts/delegated-accounts-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/widget-auth-context/widget-auth-context-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/storage-model/storage-model-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/auth/auth-selector-README.md
---
# Connection Hub Solution

Connection Hub is the solution component that lets KDCube connect identities,
request proofs, platform authority, and delegated external accounts without
collapsing those concepts into one store or one auth trick.

It has six roles:

```text
Connection Hub
  |
  +-- Identity Links
  |     external identity -> platform principal
  |
  +-- Request Authenticators
  |     request proof -> verified external identity
  |
  +-- Authority Projection
  |     actor identity + linked platform principal -> UserSession authority
  |
  +-- Delegated Accounts
  |     platform user -> external account token/capability
  |
  +-- Link Flows
  |     platform-first and channel-first linking
  |
  +-- Widget/Auth Context Transport
        host iframe/server config -> promoted auth headers
```

## One Mental Model

```text
incoming world event/request/widget call
       |
       | proof material
       |   browser cookies / Telegram initData / Slack signature / API key
       v
Request Authenticators
       |
       | verified external identity
       |   telegram:434804821
       v
Identity Links
       |
       | linked platform principal
       |   02e53484-...
       v
Authority Projection
       |
       | UserSession + identity_authority
       |   actor_user_id=telegram_434804821
       |   platform_user_id=02e53484-...
       |   user_type=privileged
       v
KDCube app/API/runtime/ReAct/economics
```

Delegated accounts are a separate side of the same hub:

```text
platform user 02e53484-...
       |
       v
Delegated Accounts
       |
       +-- Gmail OAuth token
       +-- Slack OAuth token
       +-- iCloud app password
       +-- future provider token/capability
```

An identity link proves who the actor maps to in KDCube. A delegated account
token lets automation act on a remote account. Do not use delegated account
tokens as platform identity proof, and do not derive platform roles from
provider-local roles.

## Reading Order

| Need | Read |
| --- | --- |
| Understand the complete map | This document |
| Store and resolve external identity -> platform user | [Identity Links](identity-links/identity-links-README.md) |
| User starts in Telegram/Slack/etc. and then attaches to KDCube | [Channel-First Identity Linking](link-flows/channel-first-identity-linking-README.md) |
| User starts in KDCube and then proves a provider identity | [Platform-First Identity Linking](link-flows/platform-first-identity-linking-README.md) |
| Authenticate a request with provider proof | [Request Authenticators](request-authenticators/request-authenticators-README.md) |
| Carry roles/economics across runtime boundaries | [Authority Projection](authority-projection/authority-projection-README.md) |
| Connect Gmail/Slack/iCloud for automation | [Delegated Accounts](delegated-accounts/delegated-accounts-README.md) |
| Host Connection Hub or another widget in an iframe | [Widget Auth Context](widget-auth-context/widget-auth-context-README.md) |
| Know where data/secrets live | [Storage Model](storage-model/storage-model-README.md) |
| Understand gateway-level auth selection | [Auth Selector](../../../service/auth/auth-selector-README.md) |

## Main Roundtrips

### Channel-First Identity Linking

The user starts in a context where provider auth material is already present.
Telegram Mini App is the current implemented example.

```text
Telegram Mini App has Telegram.WebApp.initData
       |
       v
host embeds Connection Hub iframe
       |
       | CONFIG_RESPONSE.authContext.headers
       |   X-Telegram-Init-Data
       |   X-KDCube-Auth-Integration-ID
       v
Connection Hub iframe calls Connection Hub
       |
       v
Connection Hub validates Telegram proof
       |
       v
creates provider-proof claim challenge
       |
       v
user opens platform claim URL in browser
       |
       v
KDCube platform sign-in if needed
       |
       v
claim endpoint writes telegram:<id> -> platform_user_id
       |
       v
Connection Hub emits Data Bus update to original iframe
```

### Platform-First Identity Linking

The user starts from a normal KDCube browser/platform session.

```text
KDCube browser session
       |
       v
Connection Hub creates challenge for current platform_user_id
       |
       v
user opens provider proof surface
       |
       v
provider proof completes challenge
       |
       v
Connection Hub writes provider:<subject> -> platform_user_id
```

### Request Authentication

The gateway/service auth side asks for a complete `UserSession`.

```text
HTTP / SSE / Socket.IO / app API request
       |
       v
RequestAuthSelector
       |
       +-- platform token/cookie auth
       |
       +-- Connection Hub bridge
             |
             v
           provider module verifies request proof
             |
             v
           identity link resolves platform principal
             |
             v
           authority projection returns roles/economics
       |
       v
UserSession
```

## Data Sources

| Data | Source | Used by |
| --- | --- | --- |
| Provider proof | Incoming request or host widget config, for example Telegram `initData` | Request authenticator module |
| Integration id | App/server config for the surface that owns the provider integration | Connection Hub selector |
| Verifier secret | Bundle secrets / secrets service via `secret_ref` | Provider verifier only |
| Identity link | Connection Hub identity-link store | Request auth, authority projection, link status |
| Platform roles | Platform principal/role resolver | Authority projection |
| Delegated account token | Connections framework user-scoped store | Automation/app tools |
| Widget auth context | Host `CONFIG_RESPONSE` | Child iframe API calls |

## Current Implementation Boundary

Current implementation:

- Telegram provider proof is implemented.
- Request-authenticator metadata is Postgres-backed.
- Identity links and identity-link challenges are currently bundle-local JSON in
  the playground app.
- Delegated Gmail/Slack/iCloud account storage uses the existing connections and
  email integration stores.
- Gateway auth selection is documented in service auth.

Production direction:

- move identity links and challenges to durable Postgres or a platform-owned
  identity service;
- keep verifier secrets only in descriptor-backed bundle secrets/secrets
  service;
- keep Connection Hub provider modules as the only place for Telegram/Slack/OIDC
  request-proof verification.

## Boundary With OAuth MCP Integration Access

Connection Hub and OAuth MCP integration access both touch platform auth, but
they are different mechanisms. The shared diagram lives in
[OAuth MCP Vs Connection Hub](../../../service/auth/design/oauth-mcp-vs-connection-hub-README.md).

Do not put Telegram/Slack/webhook proof verification into OAuth MCP. That
belongs to Connection Hub request authenticators. Do not put MCP consent,
OAuth-code issuance, refresh-token rotation, or selected-tool grants into
Connection Hub identity links. That belongs to
[OAuth MCP Integration Access](../../../service/auth/oauth-mcp-integration-access-README.md).
