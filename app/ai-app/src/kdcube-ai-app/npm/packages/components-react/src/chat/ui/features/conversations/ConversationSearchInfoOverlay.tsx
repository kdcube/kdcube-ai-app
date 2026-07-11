/** The "how ranking works" educational overlay, opened from the RANK row's ⓘ.
 *  Content mirrors the approved design: candidates → three arms → rank fusion
 *  with a worked example → presentation. Closes on ✕ or a backdrop click.
 *
 *  Rendered through a portal onto `document.body`: the sidebar/menu hosting
 *  the settings panel clips overflow (and a transformed ancestor would turn
 *  `position: fixed` into a local box), so rendering in place could clip it. */
import { createPortal } from 'react-dom'

export function ConversationSearchInfoOverlay({ onClose }: { onClose: () => void }) {
  if (typeof document === 'undefined') return null
  return createPortal(
    <div
      className="kcs-info-overlay"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className="kcs-info-panel" role="dialog" aria-modal="true" aria-label="How search ranks results">
        <div className="kcs-info-head">
          How search ranks results
          <button type="button" className="kcs-info-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="kcs-info-body">
          <div className="kcs-step">
            <div className="kcs-step-t">Step 1 — candidates (your prerequisites)</div>
            Only rows matching every filter take part — everything else never enters the pipeline:
            <div className="kcs-formula">candidates = your data ∩ WHERE (scope) ∩ WHEN (time window) ∩ HOW (kinds)</div>
          </div>
          <div className="kcs-step">
            <div className="kcs-step-t">Step 2 — three arms score the candidates, independently</div>
            <div className="kcs-arm">
              <span className="kcs-kind kcs-assistant">semantic</span>
              <span>
                <span className="kcs-arm-q">"means the same?"</span> — your query is embedded (one small guarded
                call) and compared to stored vectors. Finds “money back” when you typed “refund”; weak on exact
                codes like JM-2214.
              </span>
            </div>
            <div className="kcs-arm">
              <span className="kcs-kind kcs-you">lexical</span>
              <span>
                <span className="kcs-arm-q">"contains these words?"</span> — text matching in the database. Nails
                exact words, ticket numbers, names; misses paraphrase.
              </span>
            </div>
            <div className="kcs-arm">
              <span className="kcs-kind kcs-summary">recency</span>
              <span>
                <span className="kcs-arm-q">"how fresh?"</span> — time decay on the turn timestamp, half-life ≈ 7
                days. Pushes current work up; alone it is meaningless.
              </span>
            </div>
          </div>
          <div className="kcs-step">
            <div className="kcs-step-t">Step 3 — fusion</div>
            Each arm produces a <b>ranked list</b>; raw scores are incomparable, so fusion uses positions: an item
            ranked r-th in an arm contributes <b>weight × 1/(k + r)</b> (k ≈ 60), summed across arms. Worked example
            for “membership refund”:
            <table className="kcs-ex-table">
              <tbody>
                <tr>
                  <th></th>
                  <th>semantic</th>
                  <th>lexical</th>
                  <th>recency</th>
                  <th>fused (w = 1/1/1)</th>
                </tr>
                <tr>
                  <td>turn A</td>
                  <td>#1 (paraphrase)</td>
                  <td>#4</td>
                  <td>#5</td>
                  <td>1/61 + 1/64 + 1/65 ← wins on meaning</td>
                </tr>
                <tr>
                  <td>turn B</td>
                  <td>#3</td>
                  <td>#1 (exact words)</td>
                  <td>#6</td>
                  <td>1/63 + 1/61 + 1/66</td>
                </tr>
                <tr>
                  <td>turn C (yday)</td>
                  <td>#7</td>
                  <td>#8</td>
                  <td>#1</td>
                  <td>1/67 + 1/68 + 1/61 ← alive only via recency</td>
                </tr>
              </tbody>
            </table>
            <span className="kcs-ex-note">
              The sliders multiply each arm's contributions. Recency at 0 → freshness earns nothing. Recency at 2 →
              its votes count double. Only the ratios matter: 1/1/1 behaves exactly like 2/2/2.
            </span>
          </div>
          <div className="kcs-step">
            <div className="kcs-step-t">Step 4 — presentation</div>
            Top hits return with their turn ids and snippets; the list groups them by conversation. The relevance %
            is each hit's fused score relative to the best hit of this search.
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
