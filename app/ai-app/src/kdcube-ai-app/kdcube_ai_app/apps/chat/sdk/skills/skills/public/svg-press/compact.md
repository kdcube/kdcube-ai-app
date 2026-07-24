Hand-craft self-contained SVG diagrams (custom layout, nested boxes, badges, mixed arrows) that render identically in browsers, `<img>` tags, and Playwright PDF/PNG.

## Structural Musts
- Pure SVG, inline styles only: no JavaScript, no external CSS, no remote assets.
- Root `<svg>`: explicit `viewBox`, `role="img"`, `aria-labelledby` pointing at `<title>` + `<desc>`, `font-family="Inter, system-ui, sans-serif"`.
- All markers, filters, gradients live in `<defs>`.
- Background `<rect>` dimensions must match the `viewBox` exactly.
- Every named box gets a subtitle line explaining what it does.
- Multi-line text = multiple `<text>` elements with incremented `y` (line height ≈ font-size × 1.3–1.4; ~13px for 9.5pt). `<foreignObject>` fails in Playwright — use stacked `<text>`.

## Containment Math — Compute, Never Eyeball
- RULE: `container_bottom >= last_child_bottom + 5` (bottom = y + height) for every container.
- Budget every row: header bar (36), boxes, pills (pill_height + gap ≈ 28px per row), subtitles.
- viewBox height = `last_element_bottom + 10..15`. Over-allocate height; shrinking is cheap, clipping is not.
- Width 820px standard (fits A4). Typical heights: three-layer 550, boundary/flow 600, component anatomy 565.

## Color Tokens (KDCube)
- Backgrounds: bg #F6FAFA · surface-2 #EEF8F7 · surface-3 #FDF9EE
- Teal #01BEB2 / dark #009C92 / pale #C6F3F1 · Blue #4372C3 / dark #2B4B8A / pale #DDEAFE
- Purple #6B63FE / pale #EBEBFF · Gold #F0BC2E / dark #C89A10 / pale #FFF8DC
- Green #52B044 / pale #E8F7E5 · Sky #38B8C8 / pale #E0F5F8
- Text #0D1E2C · text-2 #3A5672 · muted #7A99B0 · border #D8ECEB

Zone assignments: customer-owned = teal family (container #C6F3F1, inner #F0FAFA, border/header #01BEB2, badge #009C92); business value = gold; platform = blue (container #DDEAFE, inner #F0F5FF, badge #2B4B8A); integration = purple; positive callout = green pale; neutral = #EEF8F7.

Inner boxes inside colored containers use a lighter tint of the parent family (e.g. #F0FAFA inside #C6F3F1) — pure #FFFFFF only when contrast is the explicit goal.

## Text Hierarchy
- Diagram title: 18 / 800 / #2B4B8A · Section header: 12–13 / 700 / #0D1E2C
- Body/subtitle: 9.5–11 / #3A5672 · Caption: 8.5–9.5 / #7A99B0
- Badge text: 10–10.5 / 700 / #FFFFFF · Pill label: 9–10 / 600 / #2B4B8A
- Keep ≥10px padding between text and borders; smallest text (8.5pt) must read at 100% zoom.
- Disambiguate technology vs data: platform pill keeps the bare name ("Accounting"); customer-owned side takes the qualifier ("Accounting data").

## Arrows
- Marker in `<defs>`: `<marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#3A5672"/></marker>`; apply via `marker-end="url(#arrow)"`.
- Colors: data flow #3A5672 solid 1.5px · customer-owned #009C92 solid 1.5px · integration #6B63FE dashed (6,3) 2px · perimeter border #01BEB2 dashed (10,5) 2.5px.
- Bidirectional: two parallel lines offset ~10px in Y, each with the same `marker-end`; `orient="auto"` points the head along each line's direction.
- Bent/curved routes: `<path>` with `fill="none"` (L segments, or Q/C Béziers).
- Labels sit above/beside the line, offset ≥10px; in busy areas add a small neutral backing rect (#F6FAFA) under the label.
- Perimeter labels get a background rect sized text_width + ~10px so the dashed border reads cleanly.
- Shadow filter (`feDropShadow dx=0 dy=2 stdDeviation=3 flood-opacity=0.08`) on primary containers only.
- Ownership/status badge (rounded pill in the header bar) on every major container when the diagram conveys responsibility or deployment boundaries.
- Legend in a bottom corner when multiple zone colors or arrow types appear.

## Tools
### `rendering_tools.write_png` — inspection + PPTX/DOCX assets
Wrap the SVG in minimal HTML and render:

```
write_png(path="check.png", format="html",
    content="<html><body style='margin:0;background:white'>" + svg_content + "</body></html>",
    content_selector="svg", fit="content", width=1600, device_scale_factor=2)
```

- `format="html"` (default is `"mermaid"`); `content_selector="svg"` crops tightly; `fit="content"` tight crop vs `"viewport"` full page; `width` 1600–2400; `device_scale_factor` 2 for inspection, 3 for final high-res; `padding_px` default 32; `background="transparent"` for alpha PNGs; `zoom` 1.2–1.8 for readability.
- PPTX/DOCX take PNG only: render at `width=2400, device_scale_factor=3`, then embed the PNG.

### `rendering_tools.write_pdf` — final document
Render the parent HTML document to PDF. Embed diagrams as inline `<svg>` for maximum fidelity, or `<img src="diagrams/arch.svg" style="width:100%;max-width:820px"/>`.

## Review Loop (mandatory for any non-trivial diagram)
1. Write the SVG with computed geometry.
2. Render to PNG with `rendering_tools.write_png`.
3. Read the PNG and check: containment (nothing past its parent), viewBox matches background / no edge clipping, arrowhead directions, labels clear of strokes, inner fills tinted, subtitles present, ownership badges present, technology/data disambiguated, 8.5pt text legible, marker IDs unique when multiple SVGs inline in one HTML page (same IDs are fine when each SVG is isolated in its own `<img>`).
4. Fix, re-render, repeat until all checks pass — only then embed into the final document.

## Quick Fixes
- Clipped bottom → recompute `last_child_bottom`, add 10–15px height.
- Pills overflow → budget 28px per pill row, grow the container.
- Washed out → stronger container border, one darker header bar, inner cards lighter than container.
- Marker missing in PDF → `marker-end` referenced another inlined SVG's ID; make IDs unique or isolate per `<img>`.
