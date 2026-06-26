---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connections-sdk-solution-README.md
title: "Connections SDK Solution"
summary: "Identity links, connected external accounts, and authority projection from channel identities into KDCube execution context."
tags: ["sdk", "solutions", "connections", "identity", "auth", "authority", "telegram", "automations"]
updated_at: 2026-06-26
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/authenticators-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/auth/auth-selector-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/automations/automations-sdk-solution-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/runtime/cross-runtime-context-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/auth/auth-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/auth/bundle-session-auth-README.md
---
# Connections SDK Solution

Connections is the solution layer for joining identities and accounts without
collapsing them into one thing.

It covers two related but different stories:

- identity links: `telegram:434804821` is the same human/platform principal as
  `02e53484-...`;
- connected accounts: the user grants automation access to a remote account,
  such as Gmail, Slack, iCloud, or another service.

The first story is about **who is acting and which platform authority they can
use**. The second story is about **which external resources an app/agent may
operate on**.

## Terminology

| Term | Meaning |
| --- | --- |
| Channel identity | Identity proven by the current surface or transport, for example `telegram:434804821`, `google:user@example.com`, `api-key:<fingerprint>`. |
| Actor identity | The identity that initiated the current execution. For Telegram-owned storage this may be `telegram_434804821`. |
| Platform principal | KDCube platform user id that owns platform roles, permissions, subscriptions, budgets, and admin authority. |
| Connected account | A delegated external resource account, such as Gmail or Slack, that an app/agent may use with consent. |
| Authority projection | The one-time conversion from actor/channel identity to effective platform roles and economics identity for this execution. |
| Connection Hub request-auth bridge | Gateway/SDK adapter that passes a request envelope to Connection Hub and receives linked authority back. |
| Connection Hub provider module | Provider-specific verifier inside Connection Hub, for example Telegram, Slack, webhook HMAC, API key, Gmail/OIDC. Modules have access to Connection Hub config, secrets, and identity-link data. |

## The Three Layers

```text
1. Authentication / proof
   "This request really came from Telegram user 434804821."

2. Link resolution
   "telegram:434804821 is linked to platform user 02e53484-..."

3. Authority projection
   "This execution acts as telegram_434804821, but role/economics authority is
    platform user 02e53484-... with roles [kdcube:role:super-admin]."
```

These layers should not be mixed.

Surface-local roles are not platform roles. For example, a Telegram-local
`admin` row can authorize a Telegram Mini App action, but it must not become
`kdcube:role:super-admin`. Platform authority must come from the linked platform
principal and the platform authority resolver.

## Runtime Shape

When a channel identity is linked to a platform principal, execution context
should carry both identities:

```text
REQUEST_CONTEXT.user
  user_id     = telegram_434804821       # actor/storage identity
  user_type   = privileged               # effective platform authority
  roles       = ["kdcube:role:super-admin"]
  permissions = [...]

BUNDLE_CALL_CONTEXT.identity_authority
  actor_user_id       = telegram_434804821
  storage_user_id     = telegram_434804821
  platform_user_id    = 02e53484-0081-70ce-11c1-e96706b1a182
  economics_user_id   = 02e53484-0081-70ce-11c1-e96706b1a182
  user_type           = privileged
  economics_user_type = privileged
  platform_roles      = ["kdcube:role:super-admin"]
  platform_permissions = [...]
  identity_provider   = telegram
  identity_provider_subject = 434804821
```

`REQUEST_CONTEXT.user` is what generic role validators see. `BUNDLE_CALL_CONTEXT.identity_authority`
preserves provenance and the actor/economics split across runtime boundaries.

This is documented as part of the portable room in
[Cross-Runtime Context](../../runtime/cross-runtime-context-README.md).

## Current SDK Mechanism

The current implementation lives in:

```text
kdcube_ai_app.apps.chat.sdk.identity_authority
```

Important helpers:

| Helper | Purpose |
| --- | --- |
| `resolve_platform_authority(...)` | Given an actor identity and linked platform user id, return a JSON-safe authority envelope. |
| `normalize_execution_authority(...)` | Normalize an authority envelope before storing it in a queued job source or `bundle_call_context`. |
| `apply_authority_to_comm_context(...)` | Stamp effective role/permissions into `REQUEST_CONTEXT.user` before tools/ReAct run. |

Request-facing authentication is documented separately in
[Connection Authenticators](authenticators-README.md). That layer takes a raw
request envelope, calls Connection Hub, lets Connection Hub select a provider
module, verifies provider proof, resolves identity links, and returns authority
material that the gateway turns into a `UserSession`.

Automations use this through:

```python
from kdcube_ai_app.apps.chat.sdk.solutions.automations import due

due.configure_due_automations(
    storage_root_or_error=storage_root_or_error,
    automation_operations_module=automation_operations,
    scheduler_identity_resolver=my_identity_context_resolver,
)
```

The resolver is app/channel-specific only at the proof/link layer. It should
answer: "for this actor, which platform principal is linked?" It should not
invent platform roles.

## Surfaces

| Surface | How it should work |
| --- | --- |
| Browser REST/SSE/Socket.IO | Normal platform auth creates `UserSession`; roles are already present in request context. |
| Telegram-hosted widgets | The Telegram host passes `telegramInitData` through the standard `CONFIG_RESPONSE`; the widget sends `X-Telegram-Init-Data` on normal app operations. Gateway auth flows through the Connection Hub bridge; the Telegram module resolves the linked platform principal and stamps authority before protected app work. |
| App-owned Telegram public routes | Use only when the app intentionally exposes a Telegram-specific public API. The route must still validate Telegram proof and resolve authority; do not treat public static widget loading as public data/action authorization. |
| Telegram webhook | Webhook signature/bot token proves the channel event. The Connection Hub Telegram module should resolve the Telegram identity to platform authority if platform roles/economics are needed. |
| Scheduled automations | Supported now through `scheduler_identity_resolver`; authority is stored in durable job source and rebound when the job runs. |
| Manual queued jobs | If the request starts from a platform browser session, roles are already present. If it queues detached work for a surface actor, the queue source should carry `identity_authority`. |
| Data Bus | Messages must carry enough actor/auth metadata for Connection Hub or the producing provider to stamp authority before trusted work. |
| MCP/API integration tokens | Integration tokens should authenticate as a platform principal or be resolved through the same Connection Hub bridge path before role checks. |

## Request-Auth Bridge

The generic request-facing mechanism is the Connection Hub request-auth bridge:

```text
incoming request/event/job
  |
  | browser cookie / Telegram initData / webhook signature / API key / MCP token
  v
request-auth selector
  |
  +-- platform token/cookie auth
  |
  +-- Connection Hub request-auth bridge
        |
        | provider module inside Connection Hub
        |   Telegram / Slack / webhook HMAC / API key / Gmail-OIDC / ...
        v
      Connection Hub data boundary
  |
  | actor identity = provider:subject
  | platform principal = Connections.resolve(actor identity)
  | roles/permissions = PlatformAuthority.resolve(platform principal)
  v
execution context
  |
  | REQUEST_CONTEXT.user carries effective roles
  | BUNDLE_CALL_CONTEXT.identity_authority carries actor/economics split
  v
app code, role checks, economics, ReAct, tools, child runtimes
```

This is platform/SDK-owned at the bridge layer and Connection-Hub-owned at the
provider-module layer. Apps should not repeat Telegram/Slack/OIDC verification;
they should pass provider proof through the request envelope and let Connection
Hub resolve authority.

## Relationship To Service Auth

`docs/service/auth` describes platform authentication providers and token
transport. Connections is higher-level:

- service auth answers "is this platform request authenticated?";
- Connections answers "which identities/accounts belong together?";
- authority projection answers "what effective platform roles/funding does this
  execution carry after the channel identity is linked?"

Do not put provider-specific identity-link policy into generic token extraction.
Token extraction belongs to service auth. Provider proof verification, link
resolution, and authority projection belong to Connection Hub provider modules
and the Connection Hub request-auth bridge.
