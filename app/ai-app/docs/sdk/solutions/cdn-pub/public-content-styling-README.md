---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/cdn-pub/public-content-styling-README.md
title: "Styling Public Catalogs (presentation contract)"
summary: "How an application styles the SDK-rendered public catalog/list surfaces: the SDK/app boundary, the --kdcpub-* design-token vocabulary and defaults, presentation.theme and presentation.stylesheets at alias and catalog level, the merge/cascade order, and the stable kdcpub-* class contract for full restyles."
tags: ["sdk", "solutions", "cdn-pub", "public-content", "catalogs", "styling", "theming", "presentation", "design-tokens"]
keywords: ["catalog styling", "presentation", "theme tokens", "kdcpub", "css variables", "stylesheets", "fold accent", "design tokens", "override styles", "bundles.yaml presentation"]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/cdn-pub/public-content-solution-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/recipes/resource_sharing/publish-discoverable-content-README.md
---
# Styling Public Catalogs (presentation contract)

The catalog/list pages under a public-content alias are **server-rendered by
the SDK** (`chat/sdk/pub/pages.py`). This document is the contract for how an
application makes those pages look like *its* product rather than the SDK's.

## The boundary

```text
SDK owns (behavior + semantic structure)
  routing, canonical URLs, sitemaps, pagination, search semantics,
  accessibility, the HTML anatomy, the stable kdcpub-* class names,
  and a neutral default theme

Application owns (presentation, declared in config)
  design tokens (colors, fonts, radii, widths) via presentation.theme
  whole stylesheets via presentation.stylesheets — loaded AFTER the SDK
  styles, so they can restyle anything the tokens don't cover
```

Every visual decision in the SDK styles is expressed as a `--kdcpub-*` CSS
variable. The SDK never hardcodes an adopter's brand; what you see with zero
configuration is only the default value of each token.

## Design tokens

`presentation.theme` is a flat `token: value` map. Each token is emitted on
`:root` as `--kdcpub-<token>` (underscores become hyphens). Unknown tokens are
emitted too — an app stylesheet may consume its own.

| Token | Default | Drives |
| --- | --- | --- |
| `bg` | `#F6FAFA` | page background (per-fold tint) |
| `surface` | `#FFFFFF` | the article band, cards, inputs, header segments |
| `ink` | `#0D1E2C` | headings, titles, primary text |
| `dim` | `#3A5672` | body/secondary text |
| `muted` | `#7A99B0` | meta text, dates, hints |
| `border` | `#D8ECEB` | hairlines, input and chip borders |
| `accent` | `#01BEB2` | row markers, active states, buttons, links |
| `accent_dark` | derived | hover/em text on light ground (derived from `accent` unless set) |
| `accent_rgb` | derived | `r,g,b` triple used for transparent tints (derived unless set) |
| `font` | Inter/system stack | body + chrome typography |
| `display` | `Georgia, 'Times New Roman', serif` | masthead title, empty-state title |
| `radius` | `10px` | segmented control, inputs, buttons (related radii derive from it) |
| `width` | `1140px` | content column (masthead, rows, header, footer) |

Token values are sanitized: a value may not contain `< >` `{ }` `;` — an
invalid token fails alias config resolution (the alias is not served
misconfigured).

The existing per-catalog `accent` / `background` / `border` fields are
shorthands for the same-named tokens and keep working unchanged.

## Where presentation is declared

Both levels accept the same object; the catalog merges over the alias:

```yaml
public_content:
  blog:
    presentation:                      # alias-wide
      stylesheets:
        - https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&display=swap
        - /assets/pub-brand.css        # app-owned public asset
      theme:
        display: "'Fraunces',Georgia,serif"
        width: 1180px
    catalogs:
      engineering:
        accent: '#01BEB2'              # shorthand == theme token
        presentation:
          theme: { bg: '#F6FAFA' }     # per-fold token overrides
```

Merge order for tokens (later wins):

```text
SDK defaults
  ← alias presentation.theme
  ← catalog accent/background/border shorthands
  ← catalog presentation.theme
```

When an override changes `accent` without providing `accent_rgb` /
`accent_dark`, both are derived from the accent hex so tints and hovers follow
automatically.

## Stylesheet cascade

Head order on every catalog page and on item pages under a catalog (the
chrome/rail shell):

```text
1. <style> SDK structural + default styles (all var-driven)
2. <style> :root { --kdcpub-* } resolved theme tokens
3. <link>  alias presentation.stylesheets (in declared order)
4. <link>  catalog presentation.stylesheets (in declared order)
```

App stylesheets therefore win the cascade at equal specificity. The
`kdcpub-*` class names are the stable selector contract: masthead
(`kdcpub-hero`, `kdcpub-eyebrow`, `kdcpub-sub`, `kdcpub-meta`), fold control
(`kdcpub-folds`, `kdcpub-fold`, `kdcpub-on`), search (`kdcpub-search`,
`kdcpub-search-hint`), the article band and rows (`kdcpub-band`,
`kdcpub-list`, `kdcpub-row`, `kdcpub-row-meta`, `kdcpub-rubric`,
`kdcpub-term`, `kdcpub-date`), pagination (`kdcpub-pager`, `kdcpub-pgbtn`,
`kdcpub-off`), the empty state (`kdcpub-empty`, `kdcpub-empty-t`), chrome
(`kdcpub-header`, `kdcpub-brand`, `kdcpub-nav`, `kdcpub-active`,
`kdcpub-foot`), and the item-page rail (`kdcpub-rail-*`).

Keep large CSS bodies in an app-owned public asset and reference it by URL;
`bundles.yaml` carries intent (tokens, URLs), not stylesheets.

## What stays fixed

Presentation never changes routes, canonical URLs, sitemap output, search
semantics, pagination behavior, or the crawlable metadata — those are the
SDK's side of the boundary. The public header stays auth-neutral: the chrome
renders only the links the config declares and carries no identity scripts.
A future renderer protocol may allow full layout replacement; until then the
token + stylesheet surface is the supported customization path.
