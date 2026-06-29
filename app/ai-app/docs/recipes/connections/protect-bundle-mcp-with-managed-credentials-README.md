---
id: repo:kdcube-ai-app/app/ai-app/docs/recipes/connections/protect-bundle-mcp-with-managed-credentials-README.md
title: "Protect Bundle MCP With Managed Credentials"
summary: "Recipe for exposing a bundle MCP surface protected by Connection Hub delegated credentials, with tool-centric grants and descriptor-owned policy."
status: active
tags: ["recipes", "connections", "connection-hub", "delegated-credentials", "mcp", "managed-auth", "bundle-surfaces"]
updated_at: 2026-06-29
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/delegated-credentials/oauth-delegated-credential-protocol-adapter-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/delegated-credentials/delegated-credential-protocol-adapters-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/bundle/bundle-platform-integration-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/configuration/bundles-descriptor-README.md
---
# Protect Bundle MCP With Managed Credentials

Use this recipe when a bundle exposes MCP tools and wants KDCube/Connection Hub
to manage external-client delegation, consent, token issuance, and tool
enforcement.

This is for cases like:

```text
Claude connects to user memories
Claude connects to KDCube knowledge
another external client connects to a narrow bundle MCP service
```

## Vocabulary

```text
mode: bundle
  Bundle owns auth itself, for example a custom shared header token.

mode: managed
  Platform/Connection Hub owns delegated credential auth.
  The bundle declares the protected surface and tool policy in descriptors.
```

MCP is the resource family, not the auth mechanism. The managed authority is:

```text
authority_id = delegated_client
authenticator_id = delegated_client.bearer
```

## Bundle Entry Point

Expose the MCP endpoint normally from the bundle:

```python
@mcp(alias="memories", route="public")
async def memories_mcp(self, request: Request, **kwargs):
    return build_memory_mcp_app(...)
```

The handler should not parse OAuth tokens itself. Managed auth is applied by the
bundle integration bridge and delegated credential guard.

## Descriptor Surface

Put the surface under `surfaces.as_provider.mcp`:

```yaml
surfaces:
  as_provider:
    mcp:
      memories:
        route: public
        auth:
          mode: managed
          authority_id: delegated_client
          identity_scope: grantor_identity_family
          tools:
            memory_search:
              grants:
                - memories:read
            memory_get:
              grants:
                - memories:read
```

Each tool declares its required grants. If one tool needs multiple grants, put
the full set on that tool:

```yaml
tools:
  admin_reindex:
    grants:
      - knowledge:read
      - knowledge:maintain
```

Do not model multi-grant tools by duplicating the tool under several grant
rows.

## Connection Hub Delegated Credential Config

Connection Hub defines which grants are delegable and which concrete resources
use them:

```yaml
connections:
  delegated_credentials:
    oauth:
      enabled: true
      public_clients:
        - client_id: claude
          redirect_uris:
            - https://claude.ai/api/mcp/auth_callback
            - http://localhost/callback
      capabilities:
        - grant: memories:read
          label: Read KDCube memories
          description: Read memory notes through delegated MCP tools.
          delegable_roles:
            - kdcube:role:chat-user
            - kdcube:role:paid
            - kdcube:role:privileged
            - kdcube:role:super-admin
      resources:
        - resource: "*/api/integrations/bundles/*/*/user-memories@2026-06-26/public/mcp/memories*"
          identity_scope: grantor_identity_family
          tools:
            memory_search:
              label: Search memories
              description: Search memory notes visible to the connected user.
              grants:
                - memories:read
            memory_get:
              label: Read one memory
              description: Read a memory note by id.
              grants:
                - memories:read
```

The capability row answers:

```text
who may delegate memories:read?
```

The resource row answers:

```text
which tools exist on this concrete MCP resource,
and which grants does each tool need?
```

## External Client Flow

```text
External client calls MCP resource
  without a delegated credential
        |
        v
MCP bridge returns protected-resource challenge
        |
        v
Client follows Connection Hub OAuth metadata
        |
        v
User signs in to KDCube and consents
        |
        v
Connection Hub issues delegated_client credential
        |
        v
Client calls MCP tools/list or tools/call with Bearer token
        |
        v
Managed guard checks:
  token valid
  resource matches
  selected tool allowed
  tool grants are present
```

## What The Bundle Receives

The bundle should receive a request whose delegated credential has already been
validated for the managed surface. Product code may still ask Connection Hub for
identity scope if it needs product aggregation:

```text
delegated_identity_scope_resolve
  credential envelope -> grantor identity / memory_user_ids
```

For example, the memories MCP resource can read the grantor identity family
when `identity_scope = grantor_identity_family`.

## Bundle-Owned MCP Can Still Exist

A bundle can expose a second MCP alias with `mode: bundle`:

```yaml
surfaces:
  as_provider:
    mcp:
      knowledge:
        route: operations
        auth:
          mode: bundle
          header_name: X-Knowledge-MCP-Token
```

Use this when the bundle intentionally owns a private auth contract. Use
`mode: managed` when the surface should participate in Connection Hub delegated
credentials and user consent.

## Minimal Test

```text
1. Configure a managed MCP surface with two read tools.
2. Configure Connection Hub delegated_credentials.oauth capabilities/resources.
3. Call the MCP URL without Authorization.
4. Confirm the response points to Connection Hub OAuth metadata.
5. Complete OAuth from an external client.
6. Consent to only one tool if the UI allows narrowing.
7. Call the selected tool; it succeeds.
8. Call an unselected tool; it fails closed.
9. Confirm logs include delegated_client authority and selected-tool enforcement.
```

## What Not To Do

- Do not put OAuth/delegated-client config under ingress.
- Do not call this mechanism by old branch names; OAuth is only the protocol
  adapter.
- Do not hardcode tool grants in the MCP handler.
- Do not let a token with a broad grant call tools the user did not select.
- Do not use `mode: managed` for a bundle-owned shared-secret endpoint.
