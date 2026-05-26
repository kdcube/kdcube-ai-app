/**
 * Host-window coordination for the expand/collapse affordance, shared
 * idea with the stats `usage` and news `news_preview` widgets.
 *
 * When this chat UI is embedded as an iframe tile on the public landing
 * page, the expand control asks the host to promote the same iframe to a
 * fullscreen overlay (no reload, no re-fetch — the app keeps its state).
 * The widget never opens a fullscreen layer itself, since an iframe
 * cannot draw outside its own rectangle.
 *
 * Contract:
 *   widget -> host: { type: 'kdcube-widget-view', widget: 'versatile',
 *                     view: 'compact' | 'expanded' }
 *   host -> widget: { type: 'kdcube-set-view', view: 'compact' | 'expanded' }
 */

export type VersatileHostView = 'compact' | 'expanded'

export function requestHostView(view: VersatileHostView): void {
  try {
    if (typeof window === 'undefined' || window.parent === window) return
    window.parent.postMessage({ type: 'kdcube-widget-view', widget: 'versatile', view }, '*')
  } catch {
    // Non-fatal: the iframe simply stays at its embedded size.
  }
}
