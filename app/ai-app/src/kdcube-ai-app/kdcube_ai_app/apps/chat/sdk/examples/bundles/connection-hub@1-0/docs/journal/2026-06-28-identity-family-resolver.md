---
id: kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/connection-hub@1-0/docs/journal/2026-06-28-identity-family-resolver.md
title: "2026-06-28 - Identity Family Resolver"
summary: "Connection Hub now exposes a resolver facet that expands an actor/platform user into the linked identity family and canonical user ids for server-side aggregation."
status: active
tags: ["connection-hub", "identity", "resolver", "memories", "linked-identities"]
---

# 2026-06-28 - Identity Family Resolver

## Summary

Connection Hub now exposes the SDK-owned linked-identity expansion needed by
product surfaces such as memories. The resolver implementation lives in
`kdcube_ai_app.apps.chat.sdk.solutions.connections.hub.resolver`; this bundle
only publishes it as an API operation. Consumers should not parse Telegram ids,
manually query identity-link files, or trust client-provided user-id lists.

The new resolver operation is:

```text
identity_family_resolve
```

It answers:

```text
current actor/platform user
  -> platform authority identity, if linked
  -> provider/integration identities
  -> canonical user ids for aggregation
```

## Shape

For a linked Telegram actor, the resolver returns:

```json
{
  "schema": "connection_hub.identity_family.v1",
  "linked": true,
  "platform_user_id": "02e...",
  "authority": {
    "kind": "authority",
    "authority_id": "platform",
    "provider": "platform",
    "user_id": "02e..."
  },
  "identities": [
    {
      "kind": "authority",
      "authority_id": "platform",
      "provider": "platform",
      "user_id": "02e..."
    },
    {
      "kind": "integration",
      "provider": "telegram",
      "provider_subject": "100200300",
      "user_id": "telegram_100200300",
      "integration_id": "telegram.kdcube_ref"
    }
  ],
  "memory_user_ids": ["02e...", "telegram_100200300"]
}
```

`memory_user_ids` is intentionally server-facing. The memories backend can use
it to aggregate rows across linked identities. The memories widget must not
provide arbitrary owner ids.

## Access Rule

The resolver only returns the family for the current platform user or the
current authenticated actor. If a platform session asks for another platform
user's family, it is denied. If an external actor session asks for a different
actor, it is denied.

## First Consumer

The user-memories app should use this resolver before read/search/list
operations:

```text
memory request session
  -> Connection Hub identity_family_resolve
  -> memory_user_ids
  -> memory store query WHERE user_id = ANY(memory_user_ids)
```

Writes should still store under the current actor user id unless the product
explicitly changes storage ownership. Aggregation is a read-side behavior.
