Generate Markdown, HTML (with embedded SVG), or Mermaid content that renders to polished multi-page PDF via `write_pdf`, with correct page breaks and compact professional layout.

## Tool

- `rendering_tools.write_pdf` (required) — renders html or markdown content into a PDF document (Playwright + headless Chromium). Call it for every deliverable PDF. The canonical callable contract lives on the tool definition itself; this skill is authoring guidance and render-review workflow.

## Choose the Format

- **markdown** — reports, memos, documentation; standard single-column text. Fastest; a professional stylesheet is applied automatically.
- **html** — multi-column papers, magazine layouts, brochures, embedded SVG diagrams, branded collateral, precise visual control. You handle all CSS: `@page`, break rules, spacing.
- **mermaid** — one standalone diagram per PDF; pass raw Mermaid text (no ``` fences). For diagrams inside a document, create the SVG separately (use the `svg-press` skill) and embed via `<img src="diagram.svg">` in HTML mode.

## Markdown Mode

- Write standard GFM: headings, tables, lists, code fences; `![alt](relative/path.png)` images (relative to OUT_DIR).
- Citations `[[S:1,3]]` resolve automatically when sources exist; use the renderer's references option for a sources section.
- Set `landscape=True` for wide tables.
- Auto CSS covers page margins (25mm top, 20mm sides, 30mm bottom), headings, tables, code — `@page` and break rules are already handled.
- Switch to HTML when you need multi-column, SVG, or custom layout.

## HTML Mode — Page-Aware Layout

- Always define `@page { size: A4 portrait; margin: 20mm; }` (landscape: `margin: 18mm`).
- A4 portrait: ~257mm usable height (20mm margins). A4 landscape: ~177mm usable.
- Wrap each logical unit (heading + its content) in a `break-inside: avoid; page-break-inside: avoid;` container so headings stay with their text.
- Keep individual unbreakable sections under 220mm (portrait) / 150mm (landscape); split larger content into multiple breakable sections.
- Use a plain `.page` class with no automatic breaks; force breaks only via explicit `<div class="page-break"></div>` (`.page-break { page-break-after: always; }`).
- A diagram and its accompanying table/explanation MUST be in the same section — keep them on the same page.
- After composing, estimate content height per page (~250mm usable on A4). If a section is ~110% of a page, merge or tighten it so the overflow does not create a near-empty next page.
- 3-column layouts require landscape orientation; figures and headings span columns via `column-span: all` with `break-inside: avoid` on figures and tables.

## Compact Spacing (budget vertical space)

- Body: 10–10.5pt, line-height 1.5. Tables: 8.5–9.5pt, line-height 1.3, cell padding 4–7px.
- Title area top padding 8–15px; card/callout padding 8–14px, margins 7–12px; section margins 12–16px; paragraph margins 6px.
- Headers: use `border-bottom: 2px solid; padding-bottom: 6px;` (~20mm), keeping the title area lean.
- h1 18pt (up to 24pt for magazine covers), h2 13–14pt, h3 11pt.

## Height Budget (A4 portrait, 257mm usable)

- Compact header 30–40mm; executive summary 60–80mm; SVG diagram 60–80mm; table (8 rows) 50–60mm; section text 30–50mm; callout 20–30mm.
- Table row ≈ 5–6mm → max ~12–15 rows portrait, ~8–10 landscape; for longer tables, split into multiple tables each wrapped in `break-inside: avoid`.
- Diagram + table ≈ 120–140mm → fits with text on same page; if diagram + table > 200mm → give them their own page.

## Images and SVG

- Reference images and SVGs by relative file path (relative to OUT_DIR): `<img src="turn_<id>/files/chart.png">` — base64 data URIs crash headless Chromium on multi-page PDFs.
- Wrap images in figures with `break-inside: avoid`; SVGs scale to container width, viewBox aspect ratio sets rendered height.
- Bare tables split from their titles — wrap: `<div style="break-inside: avoid;"><h3>Title</h3><table>...</table></div>`.

## Wording

- Support choices by explaining what they enable; explain every entity on first use; scope ownership statements; when a term names both a technology and its data, add a "data"/"service" qualifier.

## Render-Review-Fix Loop

Always render and inspect before delivering.

1. Render PDF: `write_pdf(path="document.pdf", content=html_content, format="html")`
2. Render key visuals to PNG for inspection: `write_png(path="check-diagram.png", content=svg_content, format="html", width=1600, fit="content", content_selector="svg")`
3. Read the PDF and PNGs, checking for: blank pages (remove preceding page-break or merge sections), split content (move diagram + table into same section), overflow (increase parent height, verify viewBox), a single leaked line (reduce top padding or merge), white inner boxes in SVG (use a light tint of the parent color), labels behind arrows (offset 10+ px), ambiguous terms (add qualifier).
4. Fix and re-render. Repeat until clean. Deliver only after at least one visual inspection.
