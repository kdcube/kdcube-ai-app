# KDCube Hosting And Frame Embedding Cheat Sheet

This page is the short operational reference for `assembly.yaml` hosting and
iframe settings. The longer explanation lives in:

- `app/ai-app/docs/service/cicd/embedding-control-plane-frontend-README.md`
- `app/ai-app/docs/configuration/assembly-descriptor-README.md`

`proxy.ssl` is independent from `proxy.frame_embedding`. Set `ssl` according to
where TLS terminates in the deployment. For example, ECS/cloud deployments often
terminate HTTPS at a load balancer and keep `proxy.ssl: false` in the KDCube
nginx/OpenResty container.

## Browser Rule

Iframe policy is based on browser origin, not on a human idea of "same domain".
An origin is:

```text
scheme + host + port
```

Examples:

```text
https://dev.kdcube.tech      != https://kdcube.tech
https://app.example.com      != https://ai.example.com
https://app.example.com      != http://app.example.com
https://app.example.com      != https://app.example.com:8443
```

If the embedding page and KDCube are not the exact same origin, use
`mode: allowlist` and list the embedding page origin in `allowed_origins`.

## 1. Regular Standalone Usage

Use this for the normal current setup: users open KDCube directly, and external
sites cannot iframe the control plane.

Bundle widgets and static bundle documents still work inside the KDCube control
plane because they are same-origin frameable.

```yaml
proxy:
  ssl: false  # or true when this nginx/OpenResty instance terminates HTTPS
  route_prefix: "/platform"
  frame_embedding:
    mode: "standalone"
    allowed_origins: []
```

Effective policy:

```text
control-plane shell: X-Frame-Options DENY
bundle/widget/static docs: X-Frame-Options SAMEORIGIN
```

## 2. Embed The Control Plane In A Different Origin

Use this when the KDCube app is hosted on one origin and an external application
iframes the full control plane from another origin.

Example:

```text
KDCube:     https://ai.example.com/platform
Host app:   https://app.example.net
```

```yaml
proxy:
  ssl: false  # or true when this nginx/OpenResty instance terminates HTTPS
  route_prefix: "/platform"
  frame_embedding:
    mode: "allowlist"
    allowed_origins:
      - "https://app.example.net"
```

Multiple host apps:

```yaml
proxy:
  ssl: false  # or true when this nginx/OpenResty instance terminates HTTPS
  route_prefix: "/platform"
  frame_embedding:
    mode: "allowlist"
    allowed_origins:
      - "https://app.example.net"
      - "https://portal.example.org"
```

Effective policy:

```text
control-plane shell: CSP frame-ancestors 'self' https://app.example.net
bundle/widget/static docs: same CSP policy
```

Use origins only. Do not include paths:

```yaml
# Good
allowed_origins:
  - "https://app.example.net"

# Wrong
allowed_origins:
  - "https://app.example.net/some/path"
```

## 3. Embed The Control Plane In The Same Origin

Use this only when the parent page and KDCube are served from the exact same
origin.

Example:

```text
KDCube:     https://app.example.com/platform
Host page:  https://app.example.com/product
```

```yaml
proxy:
  ssl: false  # or true when this nginx/OpenResty instance terminates HTTPS
  route_prefix: "/platform"
  frame_embedding:
    mode: "same_origin"
    allowed_origins: []
```

Effective policy:

```text
control-plane shell: X-Frame-Options SAMEORIGIN
bundle/widget/static docs: X-Frame-Options SAMEORIGIN
```

Do not use this for different subdomains. For example, these are different
origins and require `allowlist`:

```text
https://ai.example.com       embedded by https://app.example.com
https://dev.kdcube.tech      embedded by https://kdcube.tech
```

## 4. Embed A Bundle Widget Or Bundle Main UI

Bundle widgets and bundle main UI are served as frameable KDCube document routes,
for example under:

```text
/api/integrations/bundles/...
/api/integrations/static/...
```

The current setting is deployment-wide. It does not distinguish "only widgets"
from "full control plane". If an external origin is allowed to iframe bundle
documents, the same origin is also allowed to iframe the control-plane shell.

### 4.1 Widget/Main UI Embedded By The Exact Same Origin

Example:

```text
KDCube widget: https://dev.kdcube.tech/api/integrations/bundles/.../widgets/...
Host app:      https://dev.kdcube.tech/some-page
```

Use `same_origin`:

```yaml
proxy:
  ssl: false  # or true when this nginx/OpenResty instance terminates HTTPS
  route_prefix: "/platform"
  frame_embedding:
    mode: "same_origin"
    allowed_origins: []
```

### 4.2 Widget/Main UI Embedded By Same Domain Family But Different Origin

Example:

```text
KDCube widget: https://dev.kdcube.tech/api/integrations/bundles/.../widgets/...
Host app:      https://kdcube.tech
```

These are not the same browser origin. Use `allowlist`:

```yaml
proxy:
  ssl: false  # or true when this nginx/OpenResty instance terminates HTTPS
  route_prefix: "/platform"
  frame_embedding:
    mode: "allowlist"
    allowed_origins:
      - "https://kdcube.tech"
```

### 4.3 Widget/Main UI Embedded By An Unrelated Domain

Example:

```text
KDCube widget: https://dev.kdcube.tech/api/integrations/bundles/.../widgets/...
Host app:      https://external-app.example.net
```

Use `allowlist` with that external origin:

```yaml
proxy:
  ssl: false  # or true when this nginx/OpenResty instance terminates HTTPS
  route_prefix: "/platform"
  frame_embedding:
    mode: "allowlist"
    allowed_origins:
      - "https://external-app.example.net"
```

## Quick Decision Table

| Goal | Mode | `allowed_origins` |
|---|---|---|
| Normal standalone KDCube | `standalone` | `[]` |
| Full control plane iframe on exact same origin | `same_origin` | `[]` |
| Full control plane iframe on another subdomain/domain | `allowlist` | parent app origins |
| Widget/main UI iframe on exact same origin | `same_origin` | `[]` |
| Widget/main UI iframe on another subdomain/domain | `allowlist` | parent app origins |

## Notes

- `allowed_origins` is public configuration. It is safe to keep in
  `assembly.yaml`.
- `proxy.ssl` does not decide whether browsers see HTTPS. In cloud deployments,
  browser HTTPS may be handled by the load balancer while KDCube nginx uses
  `ssl: false`.
- `allowed_origins` must contain exact origins, not wildcard domains.
- `allowlist` with an empty list is not useful; renderers downgrade it to
  same-origin behavior.
- CORS and iframe policy are different. `frame_embedding` controls whether the
  browser may frame KDCube pages. API calls may still need CORS/session/auth
  configuration depending on the embedding scenario.
