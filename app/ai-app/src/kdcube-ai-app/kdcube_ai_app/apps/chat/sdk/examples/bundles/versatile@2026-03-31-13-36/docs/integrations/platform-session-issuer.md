# Platform Session Issuer Demo

Versatile can demonstrate a bundle-owned login authority without making that
behavior a built-in default.

The bundle verifies an upstream proof, currently Telegram Mini App `initData`,
then calls the platform bundle-session authority. The platform issues and later
verifies the `kst1` session token. Versatile is the issuer surface; ingress/proc
remain the verifier.

The authority policy is not owned by Versatile. Roles, permissions, TTL,
authority id, and the `platform` flag are registered in Connection Hub under
`authority_registry.authorities`. Versatile is discovered by its registered
host operation and executes the Telegram proof exchange.

## Surface

```text
POST /api/integrations/bundles/{tenant}/{project}/versatile@2026-03-31-13-36/public/auth_telegram_session
```

The request must carry Telegram Mini App initData in the same way other
Versatile Telegram public APIs do:

```text
X-Telegram-Init-Data: <raw Telegram.WebApp.initData>
```

On success, the response sets the descriptor-configured platform auth cookies.

## Platform Descriptor

`assembly.yaml` must select bundle-session auth:

```yaml
auth:
  type: bundle
  idp: session
  auth_token_cookie_name: "__Secure-LATC"
  id_token_cookie_name: "__Secure-LITC"
  authenticators:
    platform:
      id: kdcube.bundle-session
      authority_id: kdcube.platform
      provider: session
    connection_hub:
      enabled: true
      app_id: connection-hub@1-0
      operation: request_authenticate
```

`secrets.yaml` must include the shared verifier secret:

```yaml
services:
  session_token:
    secret: "<deployment secret>"
```

Every ingress/proc worker must read the same `services.session_token.secret`.

## Connection Hub Registry

```yaml
items:
  - id: connection-hub@1-0
    config:
      authority_registry:
        authorities:
          kdcube.platform:
            label: KDCube platform authority
            platform: true
            providers:
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
```

This registry is the single source of authority policy. It can contain multiple
platform-capable authorities and multiple provider instances.

## Bundle Descriptor

`bundles.yaml` does not define platform-session policy for Versatile. It only
needs the Connection Hub pointer and the Telegram integration config used by
the hosted operation:

```yaml
items:
  - id: versatile@2026-03-31-13-36
    config:
      connections:
        connection_hub:
          bundle_id: connection-hub@1-0
      integrations:
        telegram.kdcube_ref:
          provider: telegram
          where: built-in
          enabled: true
          secret_refs:
            bot_token: integrations.telegram_kdcube_ref.definition.bot_token
            webhook_secret: integrations.telegram_kdcube_ref.definition.webhook_secret
```

`bundles.secrets.yaml` must provide the referenced Telegram secrets. These
secrets verify the upstream Telegram proof. They do not define platform grants:

```yaml
items:
  - id: versatile@2026-03-31-13-36
    secrets:
      integrations:
        telegram_kdcube_ref:
          definition:
            bot_token: "<telegram bot token>"
            webhook_secret: "<telegram webhook secret>"
```

## Responsibility Split

| Responsibility | Owner |
|---|---|
| Verify Telegram `initData` | Versatile Telegram integration |
| Register platform authority and provider instance | Connection Hub `authority_registry` |
| Choose which roles/permissions this provider may assign | Connection Hub provider instance |
| Issue `kst1` platform session token | platform bundle-session authority |
| Verify future requests | ingress/proc bundle-session auth manager |
| Store active sessions and users | platform Redis session registry |

The bundle code must not hardcode issuer roles, permissions, bot identity, or
deployment cookie names. It should resolve the provider instance from
Connection Hub by hosted operation and fail closed if the provider is missing,
disabled, not platform-capable, or not hosted by this bundle.
