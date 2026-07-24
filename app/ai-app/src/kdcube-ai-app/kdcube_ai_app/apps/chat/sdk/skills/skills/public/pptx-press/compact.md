Author slide-structured HTML that renders to native PPTX via `rendering_tools.write_pptx` (python-pptx based; only the HTML/CSS subset below is parsed — everything else is silently ignored).

## Tool
- `rendering_tools.write_pptx` — call as `write_pptx(path="deck.pptx", content=html_content)` once the full deck HTML is authored. The canonical parameter contract lives on the tool definition itself; this guide covers authoring the `content`.
- For SVG diagrams, first render to PNG with `write_png` (from svg-press): `write_png(path="diagram.png", content=svg_content, format="html", width=2400, device_scale_factor=3, fit="content", content_selector="svg")`, then embed the PNG. The PPTX renderer accepts raster images only (PNG, JPG).

## Slide structure
- Every slide is a `<section id="slide-n">`. CRITICAL: content outside `<section>` tags is silently ignored — the #1 cause of empty decks.
- `<h1>` = slide title (required, becomes the PPTX title). Optional `<p class="subtitle">` immediately after h1.
- Body: `<h2>`/`<h3>`, `<p>`, `<ul>`/`<ol>`, tables (always `<thead>` + `<tbody>`, no merged cells), callout divs, images, and `<div class="two-column">` with two `<div class="column">` children.
- Put all CSS in one `<style>` block; define colors as `:root` variables.

## Content budgets (renderer auto-scales down to ~70% min — budget to avoid it)
- Standard slide: 1 heading + 6 short bullets OR 2 paragraphs (~25–40 words each) OR 1 callout (~25–40 words).
- Two-column: each column 1 h3 + 3 bullets OR 2 short paragraphs; max ~12 lines/column; keep columns balanced.
- Table: max 6 columns, max 8 rows; concise cell text.
- Title: max 8 words (one line). Subtitle: max 12 words (one sentence).
- If content exceeds budget, split into multiple slides. One idea per slide.

## Callouts and paragraph-like divs
- Callout classes (background fill + left accent bar): `highlight-box`, `highlight`, `callout`, `warning`, `success`, `phase-box`, `comparison-item`. Any div with `border-left` styling also renders as a callout.
- Budget: max 1–2 callouts per slide, ~25–40 words each. Reserve for the most important points.
- Paragraph-like classes: `reference-link` (clickable source link), `note`, `description`.

## Supported CSS (this subset only; rest silently ignored)
- Colors: hex only (`#0066cc`) — `rgb()`, `hsl()`, and named colors are ignored.
- Typography: `font-size` (pt/px/em), `line-height`. Spacing: `padding` / per-side (px, pt, in, em/rem).
- Borders for accents only: `border-bottom` (title underline), `border-left` (callout bar).
- Two-column: `.two-column { gap: 0.3in; }`; style each `.column` individually.
- Tables: `th { background-color; color; }`, `tr:nth-child(even) { background-color; }`.
- Ignored: flex/grid, position, min/max-height, `100vh`, box-shadow, border-radius, gradients, transform/transition/animation, page-break, `* {}` resets.
- Type scale: h1 36pt, h2 28pt, h3 22pt, p/li 18pt with line-height 1.3. Stay at 14pt or larger.
- Stick to 2–3 colors per deck (primary + accent + neutrals); light backgrounds; vary layouts between slides.

## Images
- Reference by relative path from the artifact root / OUTPUT_DIR, e.g. `<img src="turn_<id>/files/chart.png" width="640">` — always file paths (base64 data URIs are rejected; remote http(s) URLs unsupported — download first).
- Size via `width="640"` (px, ~6.7in at 96dpi) or `style="width:5in; height:3in;"`. Units: px, pt, in. Oversized images auto-fit to slide width.
- Diagram sizing: full-slide `width:9in; height:5.5in`; with text above/below `width:8in; height:4in`; in one column `width:4in; height:3in`; small inline `width:3in; height:2in`.
- Visually inspect rendered PNGs before embedding — verify labels are readable.

## Citations
- Inline, immediately after the claim: `<sup class="cite" data-sids="1,3">[[S:1,3]]</sup>`. Inner `[[S:...]]` text must mirror `data-sids` (comma list or range like `2-4`). Renders as `[1] · [3]` with hyperlinks.
- Alternative footnotes block: `<div class="footnotes"><p>Sources: [[S:1]], [[S:3]]</p></div>`.
- The Sources slide is auto-generated when external sources are provided — creating one manually duplicates it. It lists external `http(s)` URLs only; generated artifacts embedded by relative `turn_...` paths stay out of it.
- Use `<sup class="cite">` for fact claims; `<div class="reference-link">` for bibliography/resource listings.

## Deck narrative
- Executive briefing (6–10 slides): title → executive summary → context → analysis (2–4) → recommendations → next steps.
- Technical (8–15 slides): title → problem → architecture diagram → detail slides (3–6) → comparison → results table → risks → recommendation + timeline.
- Alternate layouts (bullets, two-column, table, diagram); use diagrams when text alone can't convey a system.

## Render-review loop
1. Render: `write_pptx(path="deck.pptx", content=html_content)`.
2. Check slide count matches the number of `<section>` elements.
3. Inspect visually when possible; fix: blank slide → content outside `<section>` or empty section; tiny text → over budget, split the slide; missing image → verify file exists at `OUTPUT_DIR/path`; no colors → undefined CSS variable or unsupported color syntax; missing diagram → render the SVG to PNG first.
