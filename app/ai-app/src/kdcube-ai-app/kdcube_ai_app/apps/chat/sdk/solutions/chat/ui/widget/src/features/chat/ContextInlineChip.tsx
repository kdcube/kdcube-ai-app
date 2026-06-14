import { activateContextPin, contextPinActionNotice } from './contextPinActions.ts'
import type { ContextChip } from './contextChips.ts'
import type { BannerTone } from '../../service.ts'

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
      className="inline-flex cursor-pointer items-center gap-1 rounded-full border border-[var(--purple)] bg-[var(--purple-pale)] px-2 py-0.5 text-[11px] font-semibold text-[var(--purple)] hover:bg-white"
      title={typeof context.summary === 'string' ? context.summary : context.label}
      onClick={handleActivate}
    >
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M20.59 13.41 13.42 20.58a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
        <line x1="7" y1="7" x2="7.01" y2="7" />
      </svg>
      {context.label}
    </button>
  )
}
