---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/npm/components-core/engine-config-README.md
title: "Engine Config"
summary: "EngineConfig is the explicit host-supplied connection/auth contract for createChatEngine: server origin, tenant/project, app id field, auth callbacks, transport, and initial host view."
status: implementation
tags: ["sdk", "npm", "components-core", "config", "auth", "cookie", "token", "EngineRuntime"]
updated_at: 2026-06-23
keywords:
  [
    "EngineConfig",
    "EngineRuntime",
    "cookie auth",
    "token auth",
    "external login",
    "initialHostView",
  ]
---

# Engine Config

`EngineConfig` is the explicit host-supplied contract for `createChatEngine`.
The host resolves route/query/scene config first, then passes concrete values to
the engine.

```ts
interface EngineConfig {
  connection: {
    baseUrl: string
    tenant: string
    project: string
    bundleId: string
  }
  auth?: EngineAuth
  transport?: 'auto' | 'socket' | 'sse'
  initialHostView?: 'compact' | 'expanded'
}
```

`bundleId` is the current field name in the API. Treat it as the app id/version
the engine talks to.

## Auth

Login is external. The engine only carries credentials and emits
`unauthorized` when the server rejects a request.

```ts
interface EngineAuth {
  mode?: 'cookie' | 'token'
  getAccessToken?: () => string | null | Promise<string | null>
  getIdToken?: () => string | null | Promise<string | null>
  idTokenHeader?: string
}
```

- `cookie` is the default. Requests use `credentials: 'include'`.
- `token` asks the host for access/id tokens per request.

After an external login change, the host calls:

```ts
engine.refreshAuth()
```

## Transport

`transport: 'auto'` is the default. The runtime prefers Socket.IO where
available and falls back to SSE according to the engine transport code.

## Runtime

`buildRuntime(config)` derives the internal `EngineRuntime`: normalized origin,
tenant/project/app id, auth headers, token accessors, local id creation, and client
timezone. Most consumers should pass `EngineConfig` and let the engine build this.

