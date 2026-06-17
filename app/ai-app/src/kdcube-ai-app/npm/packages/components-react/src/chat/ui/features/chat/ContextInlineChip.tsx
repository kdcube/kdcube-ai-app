import type { CSSProperties } from 'react'
import type { ContextChip, BannerTone, NamespaceStyleMap } from '@kdcube/components-core/chat'
import { contextChipClass, contextChipStyle } from '@kdcube/components-core/chat'
// Activating a pin is engine-bound (needs the runtime + event bus); the engine
// surfaces any failure as a service-notice on its event bus, so the host shows
// it — the chip no longer handles the error inline.
import { useChatViewModel } from '../../context.tsx'

export function ContextInlineChip({
  context,
  namespaceStyles = {},
}: {
  context: ContextChip
  /** Retained for API compatibility; activation notices now ride the engine bus. */
  onError?: (text: string, tone?: BannerTone) => void
  namespaceStyles?: NamespaceStyleMap
}) {
  const vm = useChatViewModel()
  const handleActivate = () => {
    vm.openContextChip(context)
  }

  return (
    <button
      type="button"
      className={`k-context-chip ${contextChipClass(context)}`}
      style={contextChipStyle(context, namespaceStyles) as CSSProperties | undefined}
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
