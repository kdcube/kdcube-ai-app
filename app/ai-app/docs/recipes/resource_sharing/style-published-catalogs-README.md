---
id: repo:kdcube-ai-app/app/ai-app/docs/recipes/resource_sharing/style-published-catalogs-README.md
title: "Style Your Published Catalogs"
summary: "Step-by-step recipe for giving SDK-rendered public catalog pages your application's look: start from the fold color shorthands, override design tokens with presentation.theme, load app-owned stylesheets (fonts included) with presentation.stylesheets, add per-fold overrides, and verify the cascade — all from bundles.yaml, no SDK code."
status: active
tags: ["recipes", "resource-sharing", "public-content", "catalogs", "styling", "theming", "presentation", "design-tokens"]
updated_at: 2026-07-14
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/cdn-pub/public-content-styling-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/recipes/resource_sharing/publish-discoverable-content-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/cdn-pub/public-content-solution-README.md
---
# Style Your Published Catalogs

[Publish Discoverable Content](publish-discoverable-content-README.md) Step 8
gives your content set a browsable face — catalog pages with search,
pagination, and site chrome, rendered by the platform. This recipe makes those
pages look like **your** product.

The division of labor: the SDK renders the structure (masthead, fold control,
search, article rows, pagination, empty state) and ships a tasteful neutral
default; your application declares its presentation in config. You never fork
renderer code, and nothing here can break routing, canonicals, sitemaps, or
search — those stay on the SDK's side of the line. The full contract (every
token, defaults, cascade order, stable class names) lives in
[public-content-styling-README](../../sdk/solutions/cdn-pub/public-content-styling-README.md);
this recipe is the doing.

Worked example: a `blog` alias with `engineering` and `journal` folds.

## Step 1 — Start with the fold shorthands

Each catalog already takes three colors. This alone gives every fold its own
color world (tints and hover shades derive from the accent):

```yaml
public_content:
  blog:
    catalogs:
      engineering:
        title: Engineering
        accent: '#01BEB2'        # markers, active states, buttons, links
        background: '#F6FAFA'    # page tint
        border: '#D8ECEB'        # hairlines
      journal:
        title: Our Journal
        accent: '#0969DA'
        background: '#F4F9FF'
        border: '#D5E5F7'
```

If a recolor is all you need, stop here.

## Step 2 — Override design tokens alias-wide

Everything visual in the renderer is a `--kdcpub-*` CSS variable. Set any of
them under `presentation.theme` on the alias — typography, text colors,
surface, radius, content width:

```yaml
public_content:
  blog:
    presentation:
      theme:
        display: "'Fraunces',Georgia,serif"   # masthead / empty-state font
        font: "Inter,system-ui,sans-serif"    # body + chrome font
        ink: '#0D1E2C'                        # headings, titles
        dim: '#3A5672'                        # body text
        width: 1180px                         # content column
        radius: 8px                           # controls
```

Token values are sanitized (`< > { } ;` are rejected) and a bad token fails
the alias config — the page is never served half-styled.

## Step 3 — Load your own stylesheets (fonts included)

Tokens can't load a webfont or restructure a component. For that, declare
app-owned stylesheets — public asset URLs, loaded **after** the SDK styles
and the tokens, so your rules win the cascade:

```yaml
public_content:
  blog:
    presentation:
      stylesheets:
        - https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&display=swap
        - /assets/pub-brand.css        # your stylesheet, served by your site
      theme:
        display: "'Fraunces',Georgia,serif"
```

In `pub-brand.css`, target the stable `kdcpub-*` classes:

```css
/* your brand's masthead treatment */
.kdcpub-hero h1 { letter-spacing: -0.02em; }
/* replace the row marker dot with your own device */
.kdcpub-row::before { border-radius: 2px; }
```

Keep CSS in the asset, not in YAML — `bundles.yaml` carries intent (tokens
and URLs), never stylesheet bodies.

The **item-page rail** (the article-list control beside an article) is part
of the same contract — `kdcpub-rail-*` classes, same tokens, same stylesheet.
One rule worth stealing: the rail's fold pills stretch to share one row by
default, which squeezes long labels; natural-width wrapping reads better on
alias configs with many folds:

```css
.kdcpub-rail-folds { flex-wrap: wrap; }
.kdcpub-rail-fold  { flex: 0 1 auto; white-space: nowrap; }
```

## Step 4 — Per-fold overrides

A catalog can carry its own `presentation`. Tokens override the alias values;
stylesheets append after the alias's:

```yaml
    catalogs:
      journal:
        accent: '#0969DA'
        presentation:
          theme: { bg: '#F4F9FF' }
          stylesheets: [/assets/pub-journal.css]
```

Merge order for tokens, later wins:

```text
SDK defaults ← alias presentation.theme ← fold accent/background/border ← fold presentation.theme
```

## Step 5 — Reload and verify

Reload the app so it re-reads its config, then check the cascade with plain
`curl` — no browser needed:

```bash
curl -s https://<runtime>/…/public/__content__/blog/engineering | grep -o -- '--kdcpub-display:[^;]*'
# → --kdcpub-display:'Fraunces',Georgia,serif

curl -s https://<runtime>/…/public/__content__/blog/engineering | grep -o 'stylesheet" href="[^"]*"'
# → your stylesheets, AFTER the inline <style> blocks, alias links before fold links
```

Then eyeball both viewports (~1440 wide and ~390 wide): masthead, the fold
control, one populated fold, one empty fold, a search result page. Item pages
under the catalog pick up the same presentation automatically (the chrome and
rail shell carry it).

## What not to do

- **Don't put CSS bodies in YAML.** A stylesheet is an asset with a URL; the
  config declares which ones to load.
- **Don't restyle by patching the SDK.** Anything reachable by CSS is
  reachable through tokens + your stylesheet; if you find something that
  isn't, that is a gap to raise, not a fork to make.
- **Don't expect presentation to change behavior.** Routes, canonical URLs,
  sitemap output, search semantics, pagination, and the auth-neutral header
  are fixed; presentation is paint.
- **Don't hardcode one environment's hosts in stylesheet URLs** if the same
  descriptor serves several environments — root-relative URLs travel.

## Minimal test

```bash
curl -s $CATALOG_URL | grep -c 'link rel="stylesheet"'
# → the number of stylesheets you declared (alias + fold)
curl -s $CATALOG_URL | grep -o -- '--kdcpub-accent:[^;]*'
# → the fold's accent (the LAST match — the first is the SDK default block)
```

## Worked example

The news app's catalogs run a complete Tier-1 + Tier-2 treatment built with
this recipe — five fold color worlds plus one app stylesheet covering the
catalog pages and the rail. Its decisions (palette, stylesheet hosting,
change procedure) are recorded in the app's own
`docs/design/catalog-presentation-design.md` (applications repo). Two
practical habits from that build: **pick treatments from offline mocks
first** — replicate the rendered DOM with your candidate CSS layered last,
exactly the cascade the runtime applies — and host the stylesheet at a
root-relative URL your site serves on every origin.
