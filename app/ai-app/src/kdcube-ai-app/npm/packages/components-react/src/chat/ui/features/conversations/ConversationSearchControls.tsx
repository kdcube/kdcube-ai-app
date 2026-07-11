/**
 * Sidebar search controls: the input row (query + sliders-icon settings toggle
 * + Search button) and the collapsible settings panel with the WHERE / WHEN
 * (+ custom date range, directly underneath) / HOW / RANK rows and the scope
 * hint.
 *
 * `titles` filters the chat list locally as the user types; the deep scopes
 * only hit the backend on Search (Enter also runs it there). Escape clears
 * back to the list (and stays inside the search surface — it must not bubble
 * on to close a hosting menu/drawer).
 *
 * Layout is width-adaptive: the settings panel is a CSS container — labels sit
 * above their controls on narrow surfaces (the persistent sidebar is ~260px)
 * and move beside them from ~300px up, matching the approved mock.
 */
import type { ConversationSearchTarget, ConversationSearchWeights } from '@kdcube/components-core/chat'
import {
  SCOPE_HINTS,
  SCOPE_PLACEHOLDERS,
  type ConversationSearchScope,
  type ConversationSearchTimePreset,
  type ConversationSearchVm,
} from './useConversationSearch.ts'
import { ConversationSearchInfoOverlay } from './ConversationSearchInfoOverlay.tsx'

const SCOPES: Array<{ id: ConversationSearchScope; label: string }> = [
  { id: 'titles', label: 'Titles' },
  { id: 'current', label: 'This chat' },
  { id: 'all', label: 'All chats' },
]

const TIME_PRESETS: Array<{ id: ConversationSearchTimePreset; label: string }> = [
  { id: 'any', label: 'Any time' },
  { id: '7', label: 'Last 7 days' },
  { id: '30', label: 'Last 30 days' },
  { id: '90', label: 'Last 90 days' },
  { id: 'custom', label: 'Dates…' },
]

/** HOW pills: kind id on the wire vs. the pill label + tint class. */
const KINDS: Array<{ id: ConversationSearchTarget; label: string; tint: string }> = [
  { id: 'user', label: 'user', tint: 'kcs-you' },
  { id: 'assistant', label: 'assistant', tint: 'kcs-assistant' },
  { id: 'summary', label: 'summary', tint: 'kcs-summary' },
]

const RANK_ARMS: Array<{ id: keyof ConversationSearchWeights; label: string }> = [
  { id: 'semantic', label: 'semantic' },
  { id: 'lexical', label: 'lexical' },
  { id: 'recency', label: 'recency' },
]

export function ConversationSearchControls({
  vm,
  disabled,
}: {
  vm: ConversationSearchVm
  disabled: boolean
}) {
  return (
    <>
      <div className="kcs-search-wrap">
        <input
          type="search"
          className="k-input"
          value={vm.query}
          placeholder={SCOPE_PLACEHOLDERS[vm.scope]}
          disabled={disabled}
          onChange={(event) => vm.setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && vm.scope !== 'titles') vm.runSearch()
            if (event.key === 'Escape') {
              /* Clear the search only — don't let the Escape travel on and
               * also close a hosting overlay (the compact conversations menu). */
              event.stopPropagation()
              vm.clearSearch()
            }
          }}
        />
        <button
          type="button"
          className={`k-iconbtn ${vm.settingsOpen ? 'k-iconbtn-active' : ''}`}
          onClick={vm.toggleSettings}
          aria-label="Search settings"
          title="Search settings"
          aria-pressed={vm.settingsOpen}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="21" y1="7" x2="11" y2="7" />
            <line x1="7" y1="7" x2="3" y2="7" />
            <circle cx="9" cy="7" r="2" />
            <line x1="21" y1="17" x2="17" y2="17" />
            <line x1="13" y1="17" x2="3" y2="17" />
            <circle cx="15" cy="17" r="2" />
          </svg>
        </button>
        <button
          type="button"
          className="k-btn"
          onClick={vm.runSearch}
          disabled={disabled || vm.searching || !vm.canSearch}
        >
          {vm.searching ? 'Searching…' : 'Search'}
        </button>
      </div>

      {vm.settingsOpen ? (
        <div className="kcs-settings">
          <div className="kcs-settings-title">Search settings</div>
          <div className="kcs-row">
            <span className="kcs-lab">where</span>
            <div className="kcs-controls">
              {SCOPES.map((scope) => (
                <button
                  key={scope.id}
                  type="button"
                  className={`kcs-chip ${vm.scope === scope.id ? 'kcs-on' : ''}`}
                  onClick={() => vm.setScope(scope.id)}
                >
                  {scope.label}
                </button>
              ))}
            </div>
          </div>
          <div className="kcs-row">
            <span className="kcs-lab">when</span>
            <div className="kcs-controls">
              <select
                className="kcs-time-sel"
                value={vm.timePreset}
                onChange={(event) => vm.setTimePreset(event.target.value as ConversationSearchTimePreset)}
              >
                {TIME_PRESETS.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {vm.timePreset === 'custom' ? (
            /* Sits directly under WHEN — it refines that row's range. */
            <div className="kcs-row kcs-row-dates">
              <span className="kcs-lab" />
              <div className="kcs-controls">
                <div className="kcs-date-stack">
                  <label className="kcs-date-lab">
                    <span className="kcs-dl">from</span>
                    <input
                      type="date"
                      className="kcs-date-in"
                      value={vm.dateFrom}
                      onChange={(event) => vm.setDateFrom(event.target.value)}
                    />
                  </label>
                  <label className="kcs-date-lab">
                    <span className="kcs-dl">to</span>
                    <input
                      type="date"
                      className="kcs-date-in"
                      value={vm.dateTo}
                      onChange={(event) => vm.setDateTo(event.target.value)}
                    />
                  </label>
                </div>
              </div>
            </div>
          ) : null}
          <div className="kcs-row">
            <span className="kcs-lab">how</span>
            <div className="kcs-controls">
              {KINDS.map((kind) => {
                const on = vm.targets.includes(kind.id)
                return (
                  <button
                    key={kind.id}
                    type="button"
                    className={`kcs-kchip ${on ? `kcs-on ${kind.tint}` : ''}`}
                    onClick={() => vm.toggleTarget(kind.id)}
                    aria-pressed={on}
                  >
                    {kind.label}
                  </button>
                )
              })}
            </div>
          </div>
          <div className="kcs-row">
            <span className="kcs-lab">
              rank
              <button
                type="button"
                className="kcs-info-btn"
                onClick={() => vm.setInfoOpen(true)}
                title="How ranking works"
                aria-label="How ranking works"
              >
                i
              </button>
            </span>
            <div className="kcs-controls">
              <div className="kcs-wstack">
                {RANK_ARMS.map((arm) => (
                  <label key={arm.id} className="kcs-wrow">
                    <span className="kcs-wl">{arm.label}</span>
                    <input
                      type="range"
                      min={0}
                      max={2}
                      step={0.1}
                      value={vm.weights[arm.id]}
                      onChange={(event) => vm.setWeight(arm.id, Number(event.target.value))}
                    />
                    <span className="kcs-wv">{vm.weights[arm.id].toFixed(1)}</span>
                  </label>
                ))}
                <button type="button" className="kcs-wreset" onClick={vm.resetWeights}>
                  reset to defaults
                </button>
              </div>
            </div>
          </div>
          <div className="kcs-hint">{SCOPE_HINTS[vm.scope]}</div>
        </div>
      ) : null}

      {vm.error ? (
        <div className="px-3 pt-2">
          <div className="k-notice k-error">
            <span>{vm.error}</span>
          </div>
        </div>
      ) : null}

      {vm.infoOpen ? <ConversationSearchInfoOverlay onClose={() => vm.setInfoOpen(false)} /> : null}
    </>
  )
}
