---
id: repo:kdcube-ai-app/app/ai-app/docs/recipes/connections/host-platform-authority-in-bundle-README.md
title: "Host A Platform Authority Flow In A Bundle"
summary: "Recipe for deployments that do not want Cognito as the only platform login path: Connection Hub owns authority registration and policy, while a bundle hosts the login UI/operation and issues standard KDCube bundle-session credentials."
status: draft
tags: ["recipes", "connections", "connection-hub", "authority-registry", "bundle-session", "platform-auth", "custom-authority"]
updated_at: 2026-07-01
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/connection-hub-solution-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/connections/authority-providers/authority-provider-runtime-README.md
  - repo:kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/versatile@2026-03-31-13-36/docs/integrations/platform-session-issuer.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/auth/bundle-session-auth-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/service/auth/auth-README.md
---
# Host A Platform Authority Flow In A Bundle

Use this recipe when a deployment wants a bundle to host the user-facing login
flow while KDCube still treats the result as a normal platform session.

Examples:

```text
A customer app wants its own login page but standard KDCube sessions.
Versatile demonstrates Google login and Telegram-to-session flows.
```

The important rule:

```text
Connection Hub owns authority registration and policy.
The bundle owns only the hosted login UI/operation.
The platform verifies the issued session through standard bundle-session auth.
```

Do not put platform role policy, issuer TTL, cookie policy, or platform-ness in
bundle-local config. Register it in Connection Hub.

## Mental Model

```text
Browser opens KDCube
  no platform session
      |
      v
frontend config says auth.loginUrl = bundle hosted login page
      |
      v
Bundle login page
  Google button / custom login / Telegram session flow
      |
      v
Bundle public operation calls Connection Hub SDK runtime
      |
      v
Connection Hub registry resolves:
  platform authority
  provider instance
  upstream authenticator
  issuer settings
  grants/defaults/bootstrap rules
      |
      v
SDK runtime verifies upstream proof
      |
      v
SDK runtime issues standard kst1 bundle-session token
      |
      v
Browser receives platform auth cookies
      |
      v
Future ingress/proc requests use normal platform auth verifier
```

This is different from a channel link.

```text
Telegram initData verified by itself
  -> external actor
  -> no platform role

Bundle-hosted platform login succeeds
  -> platform subject
  -> kdcube:role:registered if no stronger role exists
```

## Platform Baseline

Any platform authority that authenticates a user and returns no roles is
normalized centrally to:

```text
kdcube:role:registered
```

This applies to Cognito, SimpleIDP, bundle-session platform providers, and
future platform authorities.

It does not apply to raw external proofs such as Telegram initData unless that
proof is consumed by a configured platform login provider.

## Assembly Descriptor

Configure the platform to use bundle-session auth. The canonical login endpoint
is declared on the authority provider as `entrypoints.login`; `auth.login_url`
is the frontend-facing pointer to that same endpoint.

```yaml
auth:
  type: bundle
  idp: session
  auth_token_cookie_name: "__Secure-LATC"
  id_token_cookie_name: "__Secure-LITC"
  login_url: "/api/integrations/bundles/<tenant>/<project>/versatile@2026-03-31-13-36/public/platform_login"
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

`login_url` is exported into frontend runtime config as `auth.loginUrl`. The
browser app uses it when it needs a platform session. It should match the
provider's `entrypoints.login` URL.

## Platform Secret

Every ingress/proc worker must share the same bundle-session verifier secret.

```yaml
services:
  session_token:
    secret: "<deployment secret>"
```

## Connection Hub Authority Registry

Register the platform authority and the provider instance hosted by the bundle.

```yaml
items:
  - id: connection-hub@1-0
    config:
      authority_registry:
        authorities:
          kdcube.platform:
            label: KDCube platform authority
            platform: true
            grants:
              subjects:
                google:<verified_google_sub>:
                  label: bootstrap_admin
                  roles:
                    - kdcube:role:super-admin
                  permissions:
                    - kdcube:*:*:*
              bootstrap_rules:
                - id: bootstrap_admin_by_google_email
                  when:
                    provider: google
                    claims:
                      email: owner@example.com
                      email_verified: true
                  roles:
                    - kdcube:role:super-admin
                  permissions:
                    - kdcube:*:*:*
            providers:
              versatile_google_session:
                type: bundle_session_login
                enabled: true
                label: Versatile Google platform session
                entrypoints:
                  login:
                    bundle_id: versatile@2026-03-31-13-36
                    route: public
                    operation: platform_login
                  session_issue:
                    bundle_id: versatile@2026-03-31-13-36
                    route: public
                    operation: auth_google_session
                  consent:
                    bundle_id: versatile@2026-03-31-13-36
                    route: public
                    operation: delegated_consent
                input:
                  authenticator_ref:
                    authority_id: google.accounts
                    provider_id: google_oidc
                issuer:
                  type: kdcube_session_token
                  ttl_seconds: 43200
                  cookie:
                    secure: true
                    same_site: lax
                grants:
                  default:
                    roles:
                      - kdcube:role:registered
                    permissions: []
                  assignable:
                    roles:
                      - kdcube:role:registered
                      - kdcube:role:super-admin
                    permissions:
                      - kdcube:*:chat:*;read;write
                      - kdcube:*:*:*

          google.accounts:
            label: Google Accounts
            platform: false
            providers:
              google_oidc:
                type: google_id_token
                enabled: true
                authenticator:
                  client_id: "<google OAuth client id>"
```

### What These Fields Mean

`kdcube.platform.platform: true`
: This authority may produce the platform subject used by platform surfaces,
  ownership projection, and economics.

`providers.versatile_google_session.type: bundle_session_login`
: This provider instance is implemented by the Connection Hub SDK
  bundle-session login runtime.

`entrypoints.login`
: The bundle-hosted browser page for this provider's sign-in UX.

`entrypoints.session_issue`
: The bundle action/callback that verifies the upstream proof and asks the
  Connection Hub SDK to issue the platform session.

`entrypoints.consent`
: Optional bundle-hosted delegated credential consent renderer. Use this when
  the product wants its own complete consent layout. The approve/deny POST
  still targets Connection Hub so CSRF, grant narrowing, authorization-code
  creation, and token issuance remain central.

`input.authenticator_ref`
: The upstream proof verifier. In the example, Google ID token verification
  lives under `google.accounts.providers.google_oidc`.

`issuer`
: The KDCube credential issued after upstream proof verification succeeds. This
  is a standard bundle-session token, not a bundle-local private token format.

`grants.default`
: Access every successful session from this provider receives.

`grants.assignable`
: Maximum roles/permissions this provider may assign through authority-level
  subject grants and bootstrap rules.

`grants.subjects`
: Stable per-subject role assignment. Use authority subjects such as
  `google:<sub>`, not email.

`grants.bootstrap_rules`
: Bootstrap mechanism for the first login when the stable subject is not known
  yet. Email can be used only as a verified claim matcher, for example Google
  `email + email_verified`.

## Bundle Descriptor

The bundle descriptor should not repeat platform-session policy. It only needs
what the hosted operation needs to run, plus the Connection Hub pointer.

```yaml
items:
  - id: versatile@2026-03-31-13-36
    config:
      connections:
        connection_hub:
          bundle_id: connection-hub@1-0
```

## Frontend Auth Descriptor

The platform frontend should not hardcode the bundle login URL. It should name
the Connection Hub authority provider and ask Connection Hub to resolve the
provider's `login` entrypoint.

```yaml
auth:
  type: bundle
  connection_hub:
    bundle_id: connection-hub@1-0
    authority_id: kdcube.platform
    provider_id: versatile_google_session
    entrypoint: login
```

At runtime the web app calls Connection Hub:

```text
POST /api/integrations/bundles/{tenant}/{project}/connection-hub@1-0/public/authority_provider_entrypoint_resolve
```

Connection Hub returns the concrete URL for the configured provider entrypoint,
for example:

```text
/api/integrations/bundles/{tenant}/{project}/versatile@2026-03-31-13-36/public/platform_login
```

This keeps route construction under Connection Hub and keeps descriptors focused
on the authority/provider contract.

For Telegram-hosted login flows, the bundle also needs the Telegram integration
secret refs. Those secrets verify the upstream Telegram proof; they do not
define platform grants.

## Bundle Code

The bundle operation should be thin. It hosts UI and delegates runtime logic to
the SDK.

```python
@api("platform_login", route="public")
async def platform_login(self, request: Request, **kwargs):
    return await platform_session_issuer.google_login_page(
        self,
        request=request,
        bundle_id=self.bundle_id,
    )

@api("auth_google_session", route="public")
async def auth_google_session(self, request: Request, **kwargs):
    payload = await request.json()
    return await platform_session_issuer.issue_google_session(
        self,
        request=request,
        credential=payload.get("credential", ""),
        bundle_id=self.bundle_id,
    )
```

The reusable implementation lives in:

```text
kdcube_ai_app.apps.chat.sdk.solutions.connections.authority_providers.bundle_session_login
```

The Versatile example wrapper lives in:

```text
kdcube_ai_app.apps.chat.sdk.examples.bundles.versatile@2026-03-31-13-36.services.platform_session_issuer
```

The bundle must not hardcode:

- platform roles;
- admin subjects;
- issuer TTL;
- cookie names;
- Google client id;
- Telegram bot identity.

Those belong to descriptors and Connection Hub registry.

## Login Page

The login page is bundle-owned UI and is registered at
`authority_registry.authorities.<platform-authority>.providers.<provider>.entrypoints.login`.
In the Versatile example, it renders Google Identity Services, posts the
credential to `auth_google_session`, and relies on the SDK runtime to set the
configured KDCube platform auth cookies.

The page may be replaced by a customer-specific login UI as long as the public
operation calls the same SDK runtime and the provider is registered in
Connection Hub.

## How To Test

1. Start an environment with `auth.type: bundle` / `auth.idp: session`.

2. Open the normal platform frontend route.

3. If there is no valid platform session, the frontend should redirect to
   `auth.login_url`.

4. Complete the hosted login flow.

5. Confirm the response sets platform auth cookies.

6. Reload the platform frontend.

7. Confirm a normal platform user can open registered-user surfaces.

8. Confirm an admin bootstrap rule grants admin only when the verified upstream
   claim matches.

9. Confirm raw Telegram Mini App auth without a platform login/link remains
   external and does not receive `kdcube:role:registered`.

## Failure Rules

The hosted operation must fail closed if:

- Connection Hub provider registration is missing;
- provider registration is disabled;
- registered authority is not `platform: true`;
- hosted operation does not match the current bundle/operation;
- upstream authenticator is missing or rejects the proof;
- subject/bootstrap grants ask for roles or permissions outside
  `grants.assignable`;
- platform session token secret is missing or inconsistent across workers.

## Related Recipes

- [Link From External Channel](link-from-external-channel-README.md)
- [Telegram Integration](integrations/telegram-README.md)
- [Delegate A KDCube Service To An External Client](delegate-kdcube-service-to-external-client-README.md)
