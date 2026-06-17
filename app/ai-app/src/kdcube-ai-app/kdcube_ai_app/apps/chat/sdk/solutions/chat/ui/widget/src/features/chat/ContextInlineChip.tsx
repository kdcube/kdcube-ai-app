import { activateContextPin, contextPinActionNotice } from './contextPinActions.ts'
import type { ContextChip } from './contextChips.ts'
import { contextChipClass, contextChipStyle } from './contextChipVisuals.ts'
import type { BannerTone } from '../../service.ts'
import { settings } from '../../settings.ts'

export function ContextInlineChip({
  context,
  onError,
}: {
  context: ContextChip
  onError?: (text: string, tone?: BannerTone) => void
}) {
  const handleActivate = () => {
    activateContextPin(context).catch((error) => {
      const notice = contextPinActionNotice(error)
      onError?.(notice.text, notice.tone)
    })
  }

  return (
    <button
      type="button"
      className={`k-context-chip ${contextChipClass(context)}`}
      style={contextChipStyle(context, settings.getNamespaceStyles())}
      title={typeof context.summary === 'string' ? context.summary : context.label}
      onClick={handleActivate}
    >
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M20.59 13.41 13.42 20.58a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
        <line x1="7" y1="7" x2="7.01" y2="7" />
      </svg>
      <span className="k-context-chip-text">
        <strong>{context.label}</strong>
      </span>
    </button>
  )
}
