---
id: repo:kdcube-ai-app/app/ai-app/docs/service/auth/design/oauth-mcp-vs-connection-hub-README.md
title: "OAuth MCP Vs Connection Hub"
summary: "Shared diagram explaining the boundary between OAuth MCP integration access and Connection Hub identity/account linkage."
status: active
tags: ["service", "auth", "oauth", "mcp", "connection-hub", "identity", "diagram"]
updated_at: 2026-06-27
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/service/auth/oauth-mcp-integration-access-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-hub-solution-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/auth/auth-selector-README.md
---
# OAuth MCP Vs Connection Hub

OAuth MCP integration access and Connection Hub both touch platform auth, but
they solve different problems.

```text
                                   KDCUBE PLATFORM AUTH
                         browser session / roles / platform user
                                          |
                    +---------------------+---------------------+
                    |                                           |
                    v                                           v

        OAUTH MCP INTEGRATION ACCESS                 CONNECTION HUB
        service/auth/oauth-mcp...                    sdk/solutions/connections
        ---------------------------                  -------------------------

        Purpose:                                    Purpose:
        give an external MCP client                 connect external identities,
        narrow access to KDCube                     request proofs, authority,
        after human consent                         and delegated accounts


        FLOW A                                      FLOW B
        External Tool Access                        External Identity / Account Linkage

        Claude Code / MCP client                    Telegram / Slack / OIDC / API key
              |                                                   |
              | discovers /mcp metadata                            | carries provider proof
              v                                                   v
        /oauth/register, /oauth/authorize            Connection Hub request authenticator
              |                                                   |
              | requires existing platform session                 | verifies provider proof
              v                                                   v
        Human platform admin consents                verified external identity
              |                                      telegram:434804821
              | scopes + selected MCP tools                        |
              v                                                   v
        auth code + PKCE token exchange              identity link lookup/write
              |                                      telegram:434804821 -> platform_user_id
              v                                                   |
        KDCube issues integration token                            v
              |                                      authority projection
              |                                      actor + platform principal -> UserSession
              v                                                   |
        external client calls /mcp                                 v
              |                                      app/API/widget/automation/ReAct/economics
              v
        selected MCP tool result


        OUTPUT                                      OUTPUT

        integration access token                    identity link
        refresh token                               request-auth authority
        selected-tool grant                         delegated account capability
        least-privilege MCP role                    UserSession + identity_authority


        STORAGE                                     STORAGE

        OAuth client records                         request-authenticator metadata
        CSRF tokens                                  identity links
        auth codes                                   link challenges
        access grants                                delegated account tokens
        refresh tokens                               verifier secret refs
        selected tool allowlist                      Data Bus link update sessions


        DO NOT MIX

        OAuth MCP is not the place                   Connection Hub is not the place
        to verify Telegram/Slack/webhook             to issue MCP OAuth consent grants
        provider proof.                              or selected-tool tokens.

        Connection Hub verifies provider             OAuth MCP issues KDCube integration
        identities and links them to                  tokens for external clients.
        platform principals.
```

Shortest mental model:

```text
OAuth MCP:
  "Can this external tool call these KDCube MCP tools after admin consent?"

Connection Hub:
  "Who is this external identity in KDCube, and what authority/account access follows?"
```

## Boundary Rules

- OAuth MCP integration access is an OAuth2 authorization-server and MCP
  protected-resource mechanism.
- Connection Hub is an identity/account linkage and request-proof authority
  mechanism.
- Connection Hub delegated OAuth accounts, such as Gmail or Slack user accounts,
  are not OAuth MCP tokens.
- OAuth MCP tokens are KDCube-issued integration access tokens for an external
  client calling KDCube MCP resources.
- Provider proof verification for Telegram/Slack/webhook/API-key belongs to
  Connection Hub request authenticators.
- MCP consent, OAuth-code issuance, refresh-token rotation, and selected-tool
  grants belong to OAuth MCP integration access.
