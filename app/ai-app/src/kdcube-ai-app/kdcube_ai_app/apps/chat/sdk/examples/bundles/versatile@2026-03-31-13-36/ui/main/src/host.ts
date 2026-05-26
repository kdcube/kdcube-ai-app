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
 *
 * Auth handoff (public embedding): the chat renders for anonymous
 * visitors but sending requires a signed-in user. When an anonymous
 * visitor tries to send, the widget asks the host to show its own login
 * surface:
 *   widget -> host: { type: 'kdcube-auth-required', widget: 'versatile' }
 * The host owns the login UI; the visitor may dismiss it and keep
 * reading. On success the host re-posts the runtime config with tokens
 * (CONFIG_RESPONSE, identity BUNDLE_VERSATILE_MAIN_VIEW), which the
 * widget picks up to open the stream — no reload.
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

export function requestAuthRequired(): void {
  try {
    if (typeof window === 'undefined' || window.parent === window) return
    /* Same-origin landing (Caddy/ngrok single origin): call the host's login
     * directly so the sign-in popup opens within the current user gesture.
     * postMessage is async, which loses the gesture and makes the browser
     * block the popup (forcing a full-page redirect). Reading the parent's
     * KDAuth throws on a cross-origin host, where we fall back to postMessage. */
    try {
      const host = (window.parent as unknown as { KDAuth?: { login?: () => void } }).KDAuth
      if (host && typeof host.login === 'function') {
        host.login()
        return
      }
    } catch {
      /* cross-origin parent — fall through to the postMessage contract */
    }
    window.parent.postMessage({ type: 'kdcube-auth-required', widget: 'versatile' }, '*')
  } catch {
    // Non-fatal: standalone (non-embedded) usage has no host to prompt.
  }
}

/**
 * True in any KDCube-hosted/dev context — standalone (top-level), or a
 * same-origin KDCube frame such as the control plane (whether the bundle
 * main view is opened top-level or iframed). Only the real public landing
 * embed is excluded: it is a *cross-origin* iframe (reading the parent
 * location throws) and drives the overlay itself.
 *
 * Used to (a) expose the dev compact/full preview toggle and (b) box the
 * compact view into a tile so the "little widget" can be assessed before the
 * landing host is wired up. On the landing embed this returns false, so the
 * compact view simply fills the host-sized iframe.
 */
export function isKdcubePreviewContext(): boolean {
  try {
    if (typeof window === 'undefined') return false
    /* Served via a public embed route (the landing page) — never a dev
     * preview, even when the landing is same-origin (Caddy/ngrok single
     * origin). Without this, the same-origin landing would read as a "preview"
     * and box the chat into a 560px dev tile inside its host-sized iframe,
     * leaving the composer below the fold. The compact view must simply fill
     * the host frame here. */
    const path = window.location.pathname || ''
    if (path.includes('/public/static') || path.includes('/public/widgets')) return false
    if (window.parent === window) return true // top-level (standalone / control-plane page)
    void window.parent.location.href // same-origin parent (control-plane iframe) is readable
    return true
  } catch {
    return false // cross-origin embed
  }
}

/**
 * Host-dropped context handoff (parent-owned drag + postMessage). The landing
 * page lets a visitor drag a "structured context" card (Why / What / How
 * KDCube) onto the chat; native HTML5 drop events don't cross the iframe
 * boundary, so the host catches the drop over a transparent overlay and hands
 * the payload over by postMessage instead:
 *
 *   host -> widget: { type: 'kdcube-context-attach',
 *                     context: { id, kind: 'kdcube-context', label, summary } }
 *
 * The chat only attaches objects it *recognizes* — a known id from this set —
 * which is the small demo of "the assistant window accepting familiar
 * surrounding objects and naming their chips."
 */
export interface RecognizedContext {
  id: string
  kind: string
  label: string
  summary?: string
}

const KNOWN_CONTEXT_IDS = new Set(['why', 'what', 'how'])

export function recognizeContextMessage(data: unknown): RecognizedContext | null {
  if (!data || typeof data !== 'object') return null
  const message = data as Record<string, unknown>
  if (message.type !== 'kdcube-context-attach') return null
  const ctx = (message.context || {}) as Record<string, unknown>
  const id = String(ctx.id || '').trim().toLowerCase()
  if (!id || !KNOWN_CONTEXT_IDS.has(id)) return null
  return {
    id,
    kind: String(ctx.kind || 'kdcube-context'),
    label: String(ctx.label || id),
    summary: ctx.summary != null ? String(ctx.summary) : undefined,
  }
}
