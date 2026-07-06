---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/delegated-accounts/delegated-accounts-README.md
title: "Delegated Provider Accounts"
summary: "Delegated Connections subtype where KDCube stores user-granted external provider claims such as Gmail, Slack, and iCloud for automation and app actions."
status: active
tags: ["sdk", "connections", "connection-hub", "delegated-connections", "delegated-accounts", "oauth", "gmail", "slack", "icloud"]
updated_at: 2026-07-06
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-hub-solution-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/delegated-connections/delegated-connections-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-edges/connection-edges-README.md
---
# Delegated Provider Accounts

Delegated provider accounts are a subtype of
[Delegated Connections](../delegated-connections/delegated-connections-README.md).
They answer this question:

```text
Can an app or automation act on this user's external account?
```

Examples:

```text
platform user 02e...
  -> Gmail OAuth token
  -> Slack OAuth token
  -> iCloud app-specific password
```

In delegated-connection terms:

```text
grantor principal
  platform user 02e...
      |
      v
delegated representative
  KDCube automation/app using provider account
      |
      v
credential plus approved claims
  Gmail OAuth token / Slack OAuth token / iCloud app password
      |
      v
resource surface
  Gmail / Slack / iCloud
```

## Boundary

Delegated provider account connections are provider credentials plus approved
claims. They are not identity proof and they are not platform roles.

```text
Identity link:
  telegram:100200300 -> platform_user_id

Delegated account:
  platform_user_id -> Gmail OAuth token

Delegated external client:
  Claude/KDCube-issued delegated_client token -> KDCube MCP resource
```

An app may use a delegated token only after normal platform/request authority is
established for the current execution.

Delegated accounts are outbound claims: KDCube uses a provider account on
behalf of the user. Managed delegated-client credentials are inbound
delegations: an external client calls a KDCube resource with a KDCube-issued
credential. Both are Connection Hub delegations, but they store and enforce
different token directions.

## Three-Level Model

```text
provider
  OAuth mechanics, no credentials
      |
      v
connector app
  connector_app_id, client_id, allowed_claims ceiling, client_secret in secrets
      |
      v
user account
  account id, access/refresh token, connected through one connector_app_id,
  approved claims for that external account/workspace
```

Multiple connector apps can exist for one provider.

```text
google
  -> connector_app_id=gmail.personal
  -> connector_app_id=gmail.enterprise

slack
  -> connector_app_id=slack.workspace_a
  -> connector_app_id=slack.workspace_b
```

## Current Providers

```text
Gmail
  generic connections framework
  OAuth through shared Connection Hub callback

Slack
  generic connections framework
  OAuth through shared Connection Hub callback

iCloud
  email integration
  app-specific password, no OAuth
```

Gmail should not be documented as an `email_*` app-password integration. Gmail
rides the generic delegated account framework.

## Runtime Use

```text
app/agent has authorized execution context
       |
       v
ConnectionsClient / named-service provider
       |
       v
Connection Hub resolves user's delegated account
       |
       v
provider credential handle returned to app-side integration code
```

The app should not ask delegated provider accounts for platform roles. Roles
come from platform authority projection.

## Credential Health And Refresh

Provider credentials stay in user secrets. Public account records expose only
metadata and health fields:

```text
credential_status
credential_kind
credential_expires_at
credential_refreshable
reconnect_required
credential_message
```

OAuth access tokens are short-lived. If a stored credential has a refresh token,
the delegated-account broker refreshes the access token before returning a
credential handle to application code. The refreshed token is written back to
user secrets.

If an OAuth credential is expired and has no refresh token, broker resolution
returns `consent_required`. The UI should present that as **Reconnect required**.
This avoids the misleading state where an account looks connected while provider
API calls fail with invalid credentials.
