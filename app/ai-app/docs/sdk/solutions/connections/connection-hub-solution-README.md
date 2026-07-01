---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-hub-solution-README.md
title: "Connection Hub Solution"
summary: "Canonical map of Connection Hub roles: connection edges, identity-family resolution, request authenticators, authority projection, delegated connections, link flows, and widget auth-context transport."
status: active
tags: ["sdk", "solutions", "connections", "connection-hub", "identity", "auth", "authority", "delegated-connections"]
updated_at: 2026-07-01
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-edges/connection-edges-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/identity-family-resolver/identity-family-resolver-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/link-flows/channel-first-connection-edge-flow-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/link-flows/platform-first-connection-edge-flow-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/request-authenticators/request-authenticators-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/authority-providers/authority-provider-runtime-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/authority-providers/credential-envelope-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/authority-projection/authority-projection-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/delegated-accounts/delegated-accounts-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/delegated-connections/delegated-connections-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/delegated-credentials/delegation-edges-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/widget-auth-context/widget-auth-context-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/storage-model/storage-model-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/auth/auth-selector-README.md
---
# Connection Hub Solution

Connection Hub is the solution component that lets KDCube connect identities,
request proofs, platform authority, and delegated connections without
collapsing those concepts into scattered auth tricks.

It has eight roles:

```text
Connection Hub
  |
  +-- Connection Edges
  |     identity -> identity delegation, same graph for links and delegates
  |
  +-- Identity Family Resolver
  |     current actor/platform user -> runtime user ids from connection edges
  |
  +-- Request Authenticators
  |     request proof -> verified external identity
  |
  +-- Authority Providers
  |     authority_id -> authenticators + grant resolver + linkers
  |
  +-- Authority Projection
  |     actor identity + resolved connection edge -> UserSession authority
  |     short-lived Data Bus tokens use that UserSession
  |
  +-- Delegated Connections
  |     credential/proof -> authenticator -> linker/grant -> allowed actions
  |
  +-- Link Flows
  |     platform-first and channel-first linking
  |
  +-- Widget/Auth Context Transport
        host iframe/server config -> promoted auth headers
```

## Descriptor Shape

Connection Hub has two related but different descriptor branches:

```yaml
config:
  identity:
    # Current request-identity mechanics.
    # This branch is intentionally narrow today.
    authenticator_selector_cache: ...
    authenticators: ...
    role_resolver: ...
    link_flows: ...

  authority_registry:
    # Canonical registry of authority realms.
    authorities:
      kdcube.platform:
        label: KDCube platform authority
        platform: true
        providers: ...
```

`identity` is the existing operational branch for request authenticators,
selector cache, role-resolution hooks, and link-flow UX. It is not the full
authority registry.

`authority_registry.authorities` is the canonical place for declaring authority
realms and provider instances. A platform authority is not a separate
descriptor kind. It is an authority with `platform: true`.

This lets one deployment register multiple platform-capable authorities without
creating one-off config keys:

```yaml
authority_registry:
  authorities:
    kdcube.platform:
      platform: true
      label: KDCube platform authority
      providers:
        cognito:
          type: cognito
          enabled: true
          authenticator:
            type: cognito_id_token

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
            cookie:
              secure: true
              same_site: lax
          grants:
            roles:
              - kdcube:role:chat-user
            permissions:
              - kdcube:*:chat:*;read;write

    telegram.kdcube_ref:
      platform: false
      label: KDCube Ref Telegram identity
      providers:
        telegram_bot_init_data:
          type: telegram_init_data
          enabled: true
          authenticator:
            secret_ref: identity.authenticators.telegram_kdcube_ref.bot_token
```

In this shape:

```text
authority -> provider instance
```

`providers.<id>` is a configured provider instance. `providers.<id>.type` is the
implementation type/enum. The id and type may match for the normal single
instance case, such as `providers.cognito.type: cognito`. They diverge only
when a deployment registers multiple instances of the same provider type, for
example `cognito_admin` and `cognito_customer`. A provider instance may have:

- `authenticator`: verifies incoming auth material;
- `issuer`: mints auth material;
- `input.authenticator_ref`: points to another authenticator used as input;
- `host`: names the bundle/API operation that executes the flow;
- `grants`: grants/roles/permissions this provider may produce.

For example, `versatile_telegram_session` is one provider instance. It consumes
Telegram initData through the Telegram authenticator and issues a KDCube bundle
session token for the platform authority.

The hosting bundle does not need a local platform-session config branch. It is
registered by its host operation:

```yaml
host:
  bundle_id: versatile@2026-03-31-13-36
  route: public
  operation: auth_telegram_session
```

If the same bundle later hosts a Google login flow, it adds another provider
instance:

```yaml
authority_registry:
  authorities:
    kdcube.platform:
      providers:
        versatile_google_session:
          type: bundle_session_login
          host:
            bundle_id: versatile@2026-03-31-13-36
            route: public
            operation: auth_google_session
          input:
            authenticator_ref:
              authority_id: google.accounts
              provider_id: google_oidc
          issuer:
            type: kdcube_session_token
            ttl_seconds: 43200
          grants: ...
```

Legacy or intermediate descriptors may still keep request authenticators under
`identity.authenticators` until that branch is migrated into
`authority_registry.authorities.*.providers.*.authenticator`.

The bundle remains the execution engine. Connection Hub remains the registry
owner for authority ids, platform-ness, provider instances, allowed grants,
TTL, and host metadata.

## One Mental Model

```text
incoming world event/request/widget call
       |
       | proof material
       |   browser cookies / Telegram initData / Slack signature / API key
       v
Connection Hub Authenticator Selector
       |
       | candidate authenticators
       v
Request Authenticator
       |
       | verified identity + authority_id
       v
Surface Guard
       |
       | same authority -> Grant Resolver
       | different authority -> Connection Edge Resolver -> Grant Resolver
       v
KDCube app/API/runtime/ReAct/economics
```

Delegated connections are the common abstraction for consented capability
relationships. The token or proof is not meaningful by itself. A registered
authenticator interprets it, and a linker/grant resolver decides which
principal, representative, resource, and actions it carries:

```text
credential / proof / token
  Telegram initData / Gmail OAuth token / iCloud password / KDCube OAuth token
       |
       v
registered authenticator
  telegram / gmail / slack / icloud / delegated_client / future provider
       |
       v
linker / grant resolver
  connection edge / delegated account grant / delegated client grant
       |
       v
allowed actions on resource surface
  Gmail / Slack / iCloud / KDCube MCP / future KDCube API
```

The visible use cases differ only by authenticator and linker:

```text
Telegram:
  initData -> telegram authenticator -> connection edge -> projected UserSession

Gmail:
  OAuth account credential -> google authenticator -> account grant -> Gmail capability

OAuth delegated credential:
  KDCube-issued token -> delegated_client authenticator -> grant registry -> integration principal + tools

Managed KDCube Services MCP:
  delegated_client credential -> kdcube-services@1-0 -> conversations / named_services tools
  named_services_list -> namespace capabilities/schema -> namespace operation
```

Connection edges prove which identity may represent which other identity, and
which grants are delegated on that relationship. Delegated connection
credentials are one edge-producing/edge-consuming use case; Telegram account
linking is another. Do not derive platform roles from provider-local roles. The
delegated representative receives only the allowed capability, not the
grantor's full platform session.

## Reading Order

| Need | Read |
| --- | --- |
| Understand the complete map | This document |
| Store and resolve identity delegation edges | [Connection Edges](connection-edges/connection-edges-README.md) |
| Resolve all linked runtime user ids for product aggregation | [Identity Family Resolver](identity-family-resolver/identity-family-resolver-README.md) |
| User starts in Telegram/Slack/etc. and then attaches to KDCube | [Channel-First Connection Edge Flow](link-flows/channel-first-connection-edge-flow-README.md) |
| User starts in KDCube and then proves a provider identity | [Platform-First Connection Edge Flow](link-flows/platform-first-connection-edge-flow-README.md) |
| Authenticate a request with provider proof | [Request Authenticators](request-authenticators/request-authenticators-README.md) |
| Understand selector/authenticator/authority/grant contracts | [Authority Provider Runtime](authority-providers/authority-provider-runtime-README.md) |
| Understand token/proof routing metadata | [Authority Credential Envelope](authority-providers/credential-envelope-README.md) |
| Carry roles/economics across runtime boundaries | [Authority Projection](authority-projection/authority-projection-README.md) |
| Open Data Bus from Telegram or another non-browser actor | [Federated Data Bus Session Tokens](../../bundle/auth-bundle-federated-README.md) |
| Understand delegated representatives and grants | [Delegated Connections](delegated-connections/delegated-connections-README.md) |
| Connect Gmail/Slack/iCloud as delegated provider accounts | [Delegated Accounts](delegated-accounts/delegated-accounts-README.md) |
| Host Connection Hub or another widget in an iframe | [Widget Auth Context](widget-auth-context/widget-auth-context-README.md) |
| Know where data/secrets live | [Storage Model](storage-model/storage-model-README.md) |
| Understand gateway-level auth selection | [Auth Selector](../../../service/auth/auth-selector-README.md) |

## Main Roundtrips

### Channel-First Connection Edge Flow

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
       |   X-KDCube-Auth-Authority-ID
       |   X-KDCube-Auth-Authenticator-ID
       v
Connection Hub iframe calls Connection Hub
       |
       v
Connection Hub authenticator selector picks the Telegram verifier
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
claim endpoint writes telegram:<id> -> platform_user_id connection edge
       |
       v
Connection Hub emits Data Bus update to original iframe
```

### Platform-First Connection Edge Flow

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
Connection Hub SDK RequestAuthResolver
       |
       +-- platform token/cookie auth
       |
       +-- ConnectionHubAuthenticationSurface
             |
             v
           selected authenticator verifies request proof
             |
             v
           verified identity + authority_id
             |
             v
           connection edge resolver resolves required authority if needed
             |
             v
           grant resolver returns roles/economics/access grants
       |
       v
UserSession
```

## Data Sources

| Data | Source | Used by |
| --- | --- | --- |
| Provider proof | Incoming request or host widget config, for example Telegram `initData` | Request authenticator module |
| Authority/authenticator hints | App/server config for the surface that owns the provider integration | Connection Hub authenticator selector |
| Verifier secret | Bundle secrets / secrets service via `secret_ref` | Provider verifier only |
| Connection edge | Connection Hub edge store | Request auth, authority projection, link status, delegation |
| Identity family | Connection Hub edge resolver | Product aggregation such as memories across connected identities |
| Platform roles | Platform principal/role resolver | Authority projection |
| Delegated connection grant | Connection Hub grant/account store | Automation/app tools or inbound protocol adapters |
| Provider account token | Connections framework user-scoped store | Automation/app tools |
| Widget auth context | Host `CONFIG_RESPONSE` | Child iframe API calls |

## Current Implementation Boundary

Current implementation:

- Telegram provider proof is implemented.
- Request-authenticator metadata is Postgres-backed.
- Connection edges and edge challenges are currently bundle-local JSON in the
  example app.
- Identity-family resolution is implemented as Connection Hub resolver logic
  over the same edge store.
- Delegated Gmail/Slack/iCloud provider account storage uses the existing
  connections and email integration stores.
- OAuth delegated credential is the current inbound delegated-connection
  protocol adapter.
- `kdcube-services@1-0` is the current built-in managed MCP example. It exposes
  `conversations` and `named_services` MCP surfaces protected by
  `delegated_client`.
- `named_services` is the current generic MCP bridge over configured
  named-service namespaces such as `mem`, `task`, and `cnv`. Its MCP server
  advertises instructions to call `named_services_list` first, then inspect
  capabilities/schema, then call search/get/write/action tools.
- MCP connector presentation is metadata, not authorization: KDCube server icons
  and `ToolAnnotations` are provided for clients such as Claude, while
  Connection Hub still enforces resource/tool/grant/identity-scope from stored
  delegated credential records.
- Gateway auth selection is documented in service auth.

Production direction:

- move connection edges and challenges to durable Postgres or a platform-owned
  identity service;
- keep verifier secrets only in descriptor-backed bundle secrets/secrets
  service;
- keep Connection Hub authenticators as the only place for Telegram/Slack/OIDC
  request-proof verification.

## Boundary With Delegated Credential Protocol Adapters

OAuth delegated credential is the current service/protocol implementation of one
delegated-connection authenticator and grant registry. It verifies KDCube-issued
integration credentials, resolves the delegated representative, and enforces
selected actions. The shared diagram lives in
[Delegated Credential Protocol Adapters](delegated-credentials/delegated-credential-protocol-adapters-README.md).

Do not put Telegram/Slack/webhook proof verification into OAuth delegated
credential. That belongs to Connection Hub request authenticators. Do not put
OAuth-code issuance, refresh-token rotation, or selected-tool grant state into
the generic edge store. That belongs to delegated connection protocol adapters
such as [OAuth delegated credential Protocol Adapter](delegated-credentials/oauth-delegated-credential-protocol-adapter-README.md).
