/** Caret SVG used by every collapsible `<details>` summary in the chat UI.
 *  Rotation animation lives in the chat CSS (`.k-workitem-caret`).
 *  Ported from the in-tree widget. */
export function CaretIcon() {
  return (
    <svg className="k-workitem-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 6l6 6-6 6" />
    </svg>
  )
}
