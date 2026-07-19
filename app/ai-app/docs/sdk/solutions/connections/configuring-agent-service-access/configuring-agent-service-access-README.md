---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/configuring-agent-service-access/configuring-agent-service-access-README.md
title: "Configuring Agent Access To Services And Accounts"
summary: "End-to-end configuration for letting an agent act on the user's behalf against KDCube named services and the user's connected external accounts: the provider side (which accounts the app can hold), the consuming-agent side (the delegated MCP connection, scopes, and namespace roster), and the runtime per-account binding (account_scope) that pins a granted agent to specific connected accounts. Names the canonical descriptor references to copy from."
status: active
tags: ["sdk", "connections", "configuration", "delegated-credentials", "named-services", "connected-accounts", "account-scope", "consent", "connection-hub", "agents", "mcp"]
updated_at: 2026-07-19
keywords: ["account_scope", "delegated: true", "named_services", "named_services_roster", "scopes", "conv:read", "delegated_to_kdcube", "connector_apps", "allowed_claims", "consent_ui", "authority_provider", "resource_grants", "kdcube-agent", "per-account scoping", "bundles.yaml", "bundles.template.yaml"]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/agent-acting-for-user/agent-acting-for-user-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/delegated-accounts/delegated-accounts-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/claim-driven-consent/claim-driven-consent-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/tools/named-services-tools-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-hub-solution-README.md
  - repo:kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/ported-langgraph-agents@2026-07-13/docs/agents/lg-react-named-services-config.md
---
# Configuring Agent Access To Services And Accounts

An agent that works on the user's behalf — reads their mail, posts to their
Slack, recalls their memory — needs two independent things configured, and they
sit in two different places:

1. **Which capability the agent may reach** — a delegated connection on the
   consuming agent, plus the app that publishes the service. This is
   **descriptor** config (`bundles.yaml`).
2. **Which of the user's connected accounts the agent may use for a provider**
   — the per-account binding (`account_scope`) on the agent's grant. This is a
   **runtime** decision the user makes in Connection Hub, not descriptor config.

The identity and consent model behind this — every agent is a per-agent
Delegated-By-KDCube client, consent is per agent, the bound token is reused each
turn, a missing grant surfaces as a one-click chat demand — is
[Agents Acting On Behalf Of The User](../agent-acting-for-user/agent-acting-for-user-README.md).
This page is the **configuration companion**: what to declare, where, and how
the account binding narrows it.

## The two consent gates (why two things are configured)

A single tool call crosses two sequential gates. Configuring "agent can use
mail" means configuring both:

```text
agent tool call
   |
   v
[Gate 1] Delegated-BY-KDCube    does THIS agent have a grant for this service?
   |  kdcube-agent:<app>:<agent>   (authored per agent in Connection Hub)
   |  passes
   v
[Gate 2] Delegated-TO-KDCube    does a connected account authorize this claim,
   |  provider account claims       AND is it one this agent is bound to?
   |  passes
   v
   the provider API call runs on the user's account
```

Gate 1 is the **agent connection + grant** (sections below, provider-agnostic).
Gate 2 is the **connected account** the user linked under Delegated-to-KDCube,
plus the agent's `account_scope` binding. The two are configured independently
and enforced in order — a granted agent still cannot touch a provider the user
has not connected, and a connected account is never enough on its own to admit
an agent.

## Surface A — publish the service (the Connection Hub app)

The app that owns Connection Hub (`connection-hub@1-0`) declares which external
providers the user can connect, under `connections.delegated_to_kdcube`:

```yaml
delegated_to_kdcube:
  enabled: true
  oauth:
    public_base_url: https://<PUBLIC_HOST>
  providers:
    google:
      label: Google
      adapter: google.oauth
      enabled: true
      connector_apps:
        gmail:
          label: Gmail
          enabled: true
          client_id: <oauth-client-id>
          client_secret_ref: connections.delegated_to_kdcube.providers.google.connector_apps.gmail.client_secret
          allowed_claims: [gmail:read, gmail:send]
      claims:
        gmail:read:  { label: Read Gmail,  provider_scopes: [..., gmail.readonly] }
        gmail:send:  { label: Send Gmail,  provider_scopes: [..., gmail.send] }
```

`allowed_claims` is the ceiling of what a connected Google account may grant;
`claims.*.provider_scopes` maps each claim to the OAuth scopes requested at
connect time. Provider/account setup itself is
[Delegated Provider Accounts](../delegated-accounts/delegated-accounts-README.md).

**Consent surface (`consent_ui`).** Optional. Absent → Connection Hub's built-in
consent renderer. Present with `mode: authority_provider` (or the equivalent
`authority_ref:` nested form) → consent is rendered through a platform authority
provider. Both are valid; pick per deployment. This is a per-environment
behavioral choice, not something to normalize across environments.

## Surface B — connect the agent to the service (the consuming agent)

The agent that consumes the service declares a delegated connection in its
`tools` list. For KDCube named services this is one connection to the
`kdcube-services@1-0` named-services MCP door, `delegated: true`, with `scopes`
as the fine-grained ceiling:

```yaml
- name: named_services
  kind: mcp
  server_id: named_services
  alias: named_services
  url: https://<PUBLIC_HOST>/api/integrations/bundles/<TENANT>/<PROJECT>/kdcube-services@1-0/public/mcp/named_services
  resource: "*/api/integrations/bundles/*/*/kdcube-services@1-0/public/mcp/named_services*"
  transport: streamable_http
  delegated: true
  scopes: [named_services:use, slack:read, slack:write, conv:read]
- name: named_services_roster       # binds no tools; teaches the prompt the realms
  kind: named_service
  alias: named_services
  namespaces:
    slack: { allowed: [provider.about, object.schema, object.search, object.action] }
    conv:  { allowed: [provider.about, object.search, object.get] }
```

Key fields:

- `delegated: true` — the connection carries the agent's consented bearer; an
  unbound connection is dropped, never called with the raw session.
- `resource` — the grant key. It must byte-match the deployment's configured
  delegated-resource id (commonly the wildcard pattern above) so grant creation,
  validation, and per-turn lookup all agree.
- `scopes` — the per-call ceiling the door's `@mcp` guard enforces; adding
  `conv:read` admits the conversation namespace and summons the prompt's
  conversation-recovery block.

This door has **two valid connection shapes** (whole-surface vs per-service) that
differ in governance granularity, consent UX, and what the prompt teaches. That
choice and the roster/scope mechanics are worked in full in the bundle's own
guide — *lg-react: Connecting Named Services — Two Config Shapes*
(`…/ported-langgraph-agents@2026-07-13/docs/agents/lg-react-named-services-config.md`,
in `see_also`) — do not re-derive it here. How namespace operations become
model-callable tools and how the agent sees the scope in its catalog is
[Named Service Tools](../../../tools/named-services-tools-README.md).

A plain (non-named-service) tool that needs a provider claim declares the
requirement inline instead, under the operation's `connections`:

```yaml
send_gmail:
  connections:
    delegated_to_kdcube:
      connected_accounts:
        - { provider_id: google, connector_app_id: gmail, claims: [gmail:send] }
```

Either way the axis the runtime resolves on is the **provider** — which is why
the account binding below keys by provider, not by namespace.

## Surface C — bind the agent to specific accounts (`account_scope`)

Surfaces A and B decide *whether* an agent may use a provider. `account_scope`
decides *which of the user's connected accounts* it may use for that provider —
so "read and write from account 1, read-only from account 2" is expressible.

This is **not** descriptor config. It lives on the agent's grant record (the
"Delegated by KDCube" card) and the user authors it in Connection Hub:

```text
account_scope: { "<provider_id>": ["<account_id>", ...] }   # a list per provider
              | { "<provider_id>": ["*"] }                   # any account (explicit)
              |  (provider key absent)                       # any account (default)
```

Semantics:

- **Keyed by `provider_id`** — the universal axis the account broker resolves on
  (a non-namespaced MCP tool and a named-service namespace both end at the same
  `provider_id`). One binding governs every claim of that provider.
- **Absent / `"*"` → any account.** Existing grants and single-account providers
  keep working unchanged; a provider with exactly one connected account resolves
  to it with no friction.
- **Read/write granularity is free — the account's own claims do it.** The card
  binds only *which account*. What that account may do is set when the user
  connects it (its per-account claims: account 2 approved `gmail:read` only, so
  an agent bound to account 2 simply cannot send). "Read+write from 1, read-only
  from 2" = the accounts' own claims + the agent's account binding.

Where the user sets it:

- **At consent** — the chat consent card's account picker. A new agent's provider
  claim presents the user's connected accounts; the user picks one or more (the
  pick is written into `account_scope` as part of the one-click grant). Zero
  connected accounts for the provider → connect one first, then pick.
- **Later** — the Edit control on the agent's "Delegated by KDCube" card, same
  picker, `replace` semantics (unchecking a provider clears its binding back to
  any-account). Because the grant card is the live authority the guard resolves
  each call, an edit applies on the agent's next call — no re-mint, no reconnect.

Enforcement is one place — the account broker intersects the candidate accounts
with the agent's allowed set before its 0/1/many decision; an explicit account
outside the set is refused, naming the allowed one. It is applied uniformly on
both the MCP-door path and the native named-service path, so the same binding
holds however the claim is resolved. Per-claim given/pending state across all of
this is the [Claim-Driven Consent](../claim-driven-consent/claim-driven-consent-README.md)
surface.

## Canonical references — copy the shape from here

Three tracked files carry the authoritative shapes. Treat the first as the
reference to copy from when wiring a new deployment or a new agent:

- **The default-install descriptor** — `app/ai-app/deployment/bundles.yaml`, the
  shipped reference (placeholder values, `<PUBLIC_HOST>/<TENANT>/<PROJECT>`). Its
  `connection-hub@1-0` entry carries Surface A; its
  `ported-langgraph-agents@2026-07-13` agent carries the Surface B connection as
  a documented, off-by-default template (both connection shapes shown inline).
- **The Connection Hub bundle template** —
  `…/examples/bundles/connection-hub@1-0/config/bundles.template.yaml`, the
  canonical `delegated_to_kdcube` provider/connector/claim block and the
  `consent_ui` options.
- **The agent's named-services config guide** (worked example, both shapes) —
  the bundle-local doc in `see_also`.

Deployed environments keep their own descriptor sets that must stay coherent
with the default-install shape on these connection points (adapt only host,
tenant, project, and per-environment secrets). Descriptor changes reach a
running environment through the platform apply path — the runtime `bundles.yaml`
and Redis views are derived, never hand-edited.

## Verify

1. **Publish** — the provider shows under *Provider connections* / *Delegated to
   KDCube* in Connection Hub, and the user can connect an account.
2. **Grant** — ask the agent to use the capability; the chat consent card
   appears with the claims and (if accounts exist) the account picker. Grant it;
   the card lands under *Delegated by KDCube* with an *agent* badge.
3. **Scope** — connect a second account of the same provider with narrower
   claims (e.g. read-only). Bind the agent to it via the picker; confirm reads
   succeed and the write it cannot authorize is refused with the connect/upgrade
   demand naming the allowed account. Re-bind to the fuller account via Edit and
   confirm the write now succeeds on the next call.
