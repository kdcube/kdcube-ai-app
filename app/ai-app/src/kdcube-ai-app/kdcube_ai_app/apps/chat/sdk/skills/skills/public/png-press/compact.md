# PNG Authoring (write_png) — Compact

Render HTML, Markdown, or Mermaid into PNG via headless Chromium with correct sizing, tight cropping, and readable text.

## Tool
- `rendering_tools.write_png` — the single rendering tool. Call it with `path`, `content`, `format`, and the sizing controls below whenever you produce a PNG.

## Format
- Mermaid diagrams: `format='mermaid'` with raw Mermaid text (no ``` fences).
- Mixed text + diagram: `format='markdown'` with fenced ```mermaid blocks; keep markdown documents small.
- Custom layout: `format='html'` with a single wrapper element (e.g. `#render-root` styled `display: inline-block` on a zero-margin white body).

## Sizing and Cropping
- Use `fit='content'` (default) to crop to the real content bounds.
- For HTML, set `content_selector` to a stable wrapper (e.g. `#render-root`).
- Add `padding_px` for margin around the crop.
- Increase viewport `width` for wide diagrams (2200–3200px typical).
- Use `zoom=1.2–1.8` when text is too small.
- Raise `device_scale_factor` (2 or 3) for crisper output.
- For Mermaid, prefer `mermaid_font_size_px` (16–22) and/or `mermaid_scale` (1.1–1.6); set `mermaid_font_family` for consistent typography.

## Layout Settling
- Mermaid and JS charts need time to settle: use `render_delay_ms=1000–2000` for complex diagrams.

## Assets
- Reference local assets under OUT_DIR using relative paths.

## Mermaid
- Provide raw Mermaid only; set `width` high enough for the diagram; increase `zoom` if the diagram is small.
- To validate Mermaid syntax visually, render to PNG and check the output for parse errors or missing nodes.
- If Mermaid syntax breaks, quote labels with punctuation and use the `public.mermaid` skill to fix labels/quotes.

## Troubleshooting
- Tiny diagram on a blank page: use `fit='content'`, provide `content_selector` for HTML, increase `zoom` and/or `width`.
- Diagram clipped on the right: increase `width` or reduce diagram complexity; keep SVG free of shrinking `max-width: 100%`.
- Text too small: `zoom=1.4–1.8`, `device_scale_factor=2` or `3`; for Mermaid, `mermaid_font_size_px` (16–22) or `mermaid_scale` (1.2–1.5).
- Mermaid fails to render: fix syntax (quote labels with punctuation); use the `public.mermaid` skill.
