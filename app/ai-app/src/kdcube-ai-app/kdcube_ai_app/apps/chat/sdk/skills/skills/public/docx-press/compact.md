Author standard Markdown that `rendering_tools.write_docx` renders into a native Word DOCX (python-docx based); the renderer applies all styling via a fixed theme.

## Tool
- `rendering_tools.write_docx` (required) — call with the finished Markdown to render the DOCX. The canonical callable contract lives on the tool definition; this skill is authoring guidance only.
- DOCX rendering is Markdown-only: headings, lists, tables, code fences, blockquotes, images, links, citation tokens. Keep to these primitives — HTML is not processed.
- Cross-skill: `write_png` (svg-press) rasterizes SVG diagrams before embedding; `write_pdf` with `format='html'` is the path for custom colors/fonts or multi-column layout.

## Document structure
- Start with `# Document Title` — the first `#` becomes the document title (Pt 22, bold, rule beneath).
- Each `## Heading` starts a major section; the renderer splits the document at `##` boundaries.
- `###`–`######` render as progressively smaller headings inside their section. 6 levels total; levels 1–3 use Word's Heading 1/2/3 styles; levels 4–6 are custom-styled, indented 0.25in per level beyond 3.
- Maintain hierarchy in order: `#` → `##` → `###` → `####`. Most documents work well with 2–4 levels; reserve `#####`/`######` for detailed technical content.

## Elements
**Paragraphs** — body Pt 11.5; `**bold**` for terms/labels, `*italic*` for emphasis.

**Lists** — `-`/`*` bullets, `1.` numbered; nest with 2 spaces per level, max 4 indent levels (deeper levels are capped).

**Tables** — pipe tables with header row plus separator row (`| --- |`, 3+ dashes per cell, required). Every row carries the same column count as the header. Columns distribute equally across the 6-inch page width; keep to 3–5 columns and put units in headers. For wider data, split into multiple tables; for side-by-side comparisons, use a table (content flows in a single column).

**Code blocks** — triple backticks with optional language; rendered in a bordered shaded box, Consolas Pt 10.5, line spacing 1.1. Best under 30 lines.

**Blockquotes** — prefix each line with `> `; renders as a shaded callout box with left accent, italic muted text. Keep to 1–3 lines.

**Links** — plain `https://…`, `http://…`, and `www.…` auto-link (`www.` gains `http://`); `[custom text](https://example.com)` for display text. Links render in the accent color.

## Images
- `![alt text](path/to/image.png)` — local file paths, resolved relative to OUT_DIR. Alt text becomes the visible caption (italic, centered), so write it descriptively.
- Centered, 6-inch max width. Formats: PNG, JPEG, GIF, BMP. A missing file renders `[Image not found: path]`.
- Remote images: download to OUT_DIR first, then reference by local path.

## SVG diagrams
Render SVG to PNG with `write_png` first, then embed the PNG:

```
write_png(
  path="diagrams/diagram-1.png",
  format="html",
  content='<html><body style="margin:0;background:white">' + svg_string + '</body></html>',
  fit="content",
  content_selector="svg",
  width=2400,
  device_scale_factor=3
)
```

Use high resolution (`width=2400`, `device_scale_factor=3`) so diagrams stay crisp in print and at high zoom.

## Citations
- Put `[[S:n]]` tokens inline after factual claims, using only source IDs that exist in the sources pool.
- Tokens resolve to the source title as a clickable hyperlink; with `include_sources_section=True` (default) a "References" section is appended: `[n] Title` + URL.

## Styling
- Palette, type scale, and mono font come from a `DocxTheme` passed to `render_docx()` at the call site (`DEFAULT_THEME` neutral, `KDCUBE_THEME` teal/blue — currently active). Markdown carries content only; describe colors per the active theme.
- Per-element custom styling, fonts, or multi-column layout: use `write_pdf` with `format='html'` instead.

## Checklist before rendering
- First line is `# Title`; sections use `##`; heading levels descend in order.
- Every table has its separator row and consistent column counts.
- Every image path is a local file under OUT_DIR; SVGs already converted to PNG.
- Citation IDs all exist in the sources pool.
