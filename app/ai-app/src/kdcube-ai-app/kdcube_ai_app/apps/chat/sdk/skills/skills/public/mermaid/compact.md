Write syntactically correct Mermaid (v11.3.0) diagrams that render without errors, styled and sized for static PNG/PDF output.

## Quoting (fixes 80% of failures)
- ALWAYS double-quote labels containing spaces, parentheses, periods, colons, commas, brackets, or special chars (`&`, `<`, `>`, `#`, `@`, `+`, `/`): `A["Process (v2.0)"]`.
- When in doubt, quote everything — overquoting is safe, underquoting breaks rendering.
- Give every multi-word node a short ID plus a quoted label: `ProcessData["Process Data"]`.
- Quote subgraph titles with spaces: `subgraph "Backend Services"`.

## Structure musts
- Declare the diagram type on line 1: `graph TB`, `graph LR`, `sequenceDiagram`, `classDiagram`, `erDiagram`, `gantt`, `stateDiagram-v2`, `pie`, `mindmap`.
- Arrows: `-->` solid, `-.->` dotted, `==>` thick, `--x` cross, `--o` circle. Exactly two dashes, no spaces inside the arrow.
- Arrow labels: `A -->|"API call"| B` or `C --"Webhook"--> D` — quote labels with special chars.
- Shape bracket pairs must match exactly: `[(` needs `)]`, `((` needs `))`, `{{` needs `}}`. Shapes: `[Rect]` `(Rounded)` `([Stadium])` `[(Database)]` `((Circle))` `{Diamond}` `{{Hexagon}}` `[/Parallelogram/]`.
- Every `subgraph` gets a matching `end` on its own line; nest at most 2 levels; nodes may link across subgraph boundaries.

Minimal flowchart skeleton:

```
graph TB
  A["Start"] --> B{"Decision"}
  B -->|"Yes"| C["Process"]
  B -->|"No"| D["Skip"]
```

## Per-type rules
- **Sequence**: declare `participant U as User`; `->>` request, `-->>` reply, `-x` lost; message text follows the colon and needs no quotes; `Note over A,B: text`; `alt`/`else`/`end`, `loop`/`end`.
- **Class**: visibility `+` public `-` private `#` protected; relations `-->` association, `--|>` inheritance, `--*` composition, `--o` aggregation; cardinality in quotes (`"1"`, `"*"`, `"0..1"`).
- **ER**: entity names are unquoted single words (underscores, not spaces); cardinality `||` exactly one, `o{` zero+, `|{` one+, `o|` zero/one; quote multi-word relationship labels after `:`.
- **Gantt**: `dateFormat` before tasks; tasks `:id, 2026-01-01, 14d` or `:id, after otherId, 7d`; task names take no quotes and no special chars; 3–5 tasks per section.
- **State**: use `stateDiagram-v2`; `[*]` is start/end; `state "Display Name" as s1` for special-char names.
- **Pie**: labels must be quoted; values are numbers.
- **Mindmap**: consistent indentation defines hierarchy; root shape `((circle))`; hierarchy is implicit (no arrows).

## Styling
- `classDef` lines go AFTER all node/edge declarations; apply with `:::className`; colors must be hex `#RRGGBB`. Properties: `fill`, `stroke`, `color`, `stroke-width`, `stroke-dasharray`.
- `%%{init: {'theme': 'base', 'themeVariables': {...}}}%%` must be the VERY FIRST line — no blank lines or comments before it. Use `theme: 'base'` when overriding themeVariables (other themes ignore overrides).
- KDCube brand tokens: primary fill `#EEF8F7`, primary border `#01BEB2` (teal), text `#0D1E2C`, secondary text/lines `#3A5672`, secondary fill `#DDEAFE` (blue-pale), tertiary fill `#FFF8DC` (gold-pale), accent `#4372C3` with `#FFFFFF` text.

```
classDef kdTeal fill:#EEF8F7,stroke:#01BEB2,color:#0D1E2C,stroke-width:2px
```

## Rendering (write_png / write_pdf, format="mermaid")
- Pass RAW Mermaid text — no ``` fences, no markdown wrapping.
- Canonical parameter contracts live on the rendering tool definitions; this skill covers authoring.
- PNG for embedding in DOCX/PPTX or visual inspection; PDF when the diagram itself is the deliverable.
- Readable output: `mermaid_font_size_px=18` or higher, `mermaid_scale=1.2–1.5`; high-res embedding: `width=2400`, `device_scale_factor=3`.
- Theme variables passed to the renderer (`mermaid_theme="base"`, `mermaid_theme_variables={...}`) style ALL diagram types, including sequence/ER/Gantt.
- Use only static features: `click` directives and links stay out of diagrams destined for PNG/PDF.

## Complexity budgets — split into multiple diagrams when over
- Flowchart: 15–20 nodes max.
- Sequence: 8 participants max.
- ER: 12 entities max.
- Split whenever the rendered PNG needs horizontal scrolling at reasonable zoom.
- Keep labels to 3–5 words; short node IDs with quoted display labels; prefer `graph LR` for pipeline-style flows.

## Validation checklist before finalizing
1. Quote check — every label with spaces/punctuation/symbols is in `"..."`.
2. Shape check — bracket pairs open and close correctly.
3. Arrow check — valid arrows (`-->`, two dashes).
4. Type check — diagram type declared on line 1.
5. Subgraph check — titles quoted, every `subgraph` has `end`.
6. classDef check — after all nodes, hex colors only.
7. Init check — `%%{init:...}%%` is line 1.
8. Fence check — raw text (no ```) for write_png/write_pdf.
9. Complexity check — within the budgets above.

## When it breaks
- Renders as plain text / parser error: quote ALL labels, then simplify.
- Error on a specific line: look for unquoted `:` `.` `()` `+` or spaces on that line.
- Colors ignored: move `classDef` after nodes; set `theme: 'base'`.
- Tiny text: raise `mermaid_font_size_px` to 18+ and `mermaid_scale` to 1.3.
