---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/link-flows/platform-first-connection-edge-flow-README.md
title: "Platform-First Connection Edge Flow"
summary: "Connection Hub flow where the user starts with an authenticated KDCube platform session and then proves an external provider identity to write an edge."
status: active
tags: ["sdk", "connections", "connection-hub", "connection-edges", "platform-session"]
updated_at: 2026-06-29
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-hub-solution-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/link-flows/channel-first-connection-edge-flow-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-edges/connection-edges-README.md
---
# Platform-First Connection Edge Flow

Platform-first edge creation starts from a normal KDCube browser/platform
session.

```text
KDCube user is already signed in
  -> user asks to connect an external identity
  -> Connection Hub creates a short-lived challenge for platform_user_id
  -> provider proof surface completes the challenge
  -> Connection Hub writes provider:<subject> -> platform:<platform_user_id>
```

## Roundtrip

```text
1. KDCube browser widget
     authenticated platform session
          |
          v
2. Connection Hub
     connection_edge_challenge_create(provider=telegram)
     stores:
       challenge_id
       target_user_id=<current platform user>
       status=pending
       expires_at
          |
          v
3. Provider proof surface
     Telegram Mini App / OAuth provider / signed verifier
     sends:
       challenge_id
       provider proof
          |
          v
4. Connection Hub authenticator module
     validates provider proof
     extracts provider_subject
          |
          v
5. Connection Hub connection-edge store
     writes:
       provider:<provider_subject> -> platform:<platform_user_id>
```

## Data Sources

| Data | Source |
| --- | --- |
| Platform user id | KDCube browser session |
| Challenge id | Connection Hub challenge store |
| Provider proof | Provider proof surface |
| Verifier secret | Bundle secrets / secrets service |
| Edge row | Connection Hub connection-edge store |

## Difference From Channel-First

```text
Platform-first:
  platform proof is known before provider proof

Channel-first:
  provider proof is known before platform proof
```

Both flows produce the same connection edge. They differ only in which side is
proven first and how the second proof is collected.
