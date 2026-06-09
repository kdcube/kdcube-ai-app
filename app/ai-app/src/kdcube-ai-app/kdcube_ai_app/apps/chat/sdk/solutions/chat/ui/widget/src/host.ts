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
 *   widget -> host: { type: 'kdcube-widget-view', widget: '<chat-widget-id>',
 *                     view: 'compact' | 'expanded' }
 *   host -> widget: { type: 'kdcube-set-view', view: 'compact' | 'expanded' }
 *
 * Auth handoff (public embedding): the chat renders for anonymous
 * visitors but sending requires a signed-in user. When an anonymous
 * visitor tries to send, the widget asks the host to show its own login
 * surface:
 *   widget -> host: { type: 'kdcube-auth-required', widget: '<chat-widget-id>' }
 * The host owns the login UI; the visitor may dismiss it and keep
 * reading. On success the host re-posts the runtime config with tokens
 * (CONFIG_RESPONSE, identity configured by the mounted bundle), which the
 * widget picks up to open the stream — no reload.
 */

import {
  CHAT_CONTEXT_ATTACH_MESSAGE,
  CHAT_CONTEXT_FOCUS_MESSAGE,
  CHAT_CONTEXT_REMOVE_MESSAGE,
  CHAT_WIDGET_ID,
} from './settings.ts'

export type TaskTrackerHostView = 'compact' | 'expanded'

export function requestHostView(view: TaskTrackerHostView): void {
  try {
    if (typeof window === 'undefined' || window.parent === window) return
    window.parent.postMessage({ type: 'kdcube-widget-view', widget: CHAT_WIDGET_ID, view }, '*')
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
    window.parent.postMessage({ type: 'kdcube-auth-required', widget: CHAT_WIDGET_ID }, '*')
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
 * Host-dropped context handoff (parent-owned drag + postMessage).
 * Native HTML5 drop events do not cross iframe boundaries reliably, so the host
 * catches drops over the chat iframe and hands recognized canvas/wizard context
 * over by postMessage instead:
 *
 *   host -> widget: {
 *     type: '<context-attach-message>',
 *     context: {
 *       id, kind: 'canvas' | 'wizard' | 'canvas.card',
 *       label, summary, ref, canvas_id, card_id
 *     }
 *   }
 *
 * Canvas is an attachable context provider. Wizard is an attachable snapshot.
 * Canvas cards attach as the proxied objects they represent. Canvas selection
 * focus, when present, comes from the attached canvas context itself.
 */
export interface RecognizedContext {
  id: string
  kind: string
  label: string
  summary?: string
  ref?: string
  logicalPath?: string
  hostedUri?: string
  mime?: string
  canvasId?: string
  canvasName?: string
  revision?: number
  cardId?: string
  cardType?: string
  selected?: boolean
  data?: Record<string, unknown>
}

function compactId(value: unknown, fallback: string): string {
  const raw = String(value || '').trim()
  return raw || fallback
}

function normalizeContext(ctx: Record<string, unknown>, index = 0): RecognizedContext | null {
  const kind = String(ctx.kind || ctx.type || '').trim()
  if (!kind) return null
  const label = String(ctx.label || ctx.title || ctx.name || kind).trim()
  const id = compactId(ctx.id || ctx.context_id || ctx.ref || ctx.logical_path, `${kind}:${index}`)
  const data = ctx.data && typeof ctx.data === 'object' ? ctx.data as Record<string, unknown> : undefined
  const revisionRaw = ctx.revision
  const revision = typeof revisionRaw === 'number'
    ? revisionRaw
    : typeof revisionRaw === 'string' && revisionRaw.trim()
      ? Number(revisionRaw)
      : undefined
  return {
    id,
    kind,
    label: label || id,
    summary: ctx.summary != null ? String(ctx.summary) : undefined,
    ref: ctx.ref != null ? String(ctx.ref) : undefined,
    logicalPath: ctx.logical_path != null ? String(ctx.logical_path) : undefined,
    hostedUri: ctx.hosted_uri != null ? String(ctx.hosted_uri) : undefined,
    mime: ctx.mime != null ? String(ctx.mime) : undefined,
    canvasId: ctx.canvas_id != null ? String(ctx.canvas_id) : undefined,
    canvasName: ctx.canvas_name != null ? String(ctx.canvas_name) : undefined,
    revision: Number.isFinite(revision) ? revision : undefined,
    cardId: ctx.card_id != null ? String(ctx.card_id) : undefined,
    cardType: ctx.card_type != null ? String(ctx.card_type) : undefined,
    selected: typeof ctx.selected === 'boolean' ? ctx.selected : undefined,
    data,
  }
}

export function recognizeContextMessage(data: unknown): RecognizedContext[] {
  if (!data || typeof data !== 'object') return []
  const message = data as Record<string, unknown>
  if (
    message.type !== CHAT_CONTEXT_ATTACH_MESSAGE &&
    message.type !== CHAT_CONTEXT_FOCUS_MESSAGE
  ) return []
  const rawContexts = Array.isArray(message.contexts)
    ? message.contexts
    : Array.isArray(message.items)
      ? message.items
      : [message.context]
  return rawContexts
    .filter((ctx): ctx is Record<string, unknown> => Boolean(ctx) && typeof ctx === 'object')
    .map((ctx, index) => normalizeContext(ctx, index))
    .filter((ctx): ctx is RecognizedContext => Boolean(ctx))
}

export function recognizeContextRemoval(data: unknown): string[] {
  if (!data || typeof data !== 'object') return []
  const message = data as Record<string, unknown>
  if (message.type !== CHAT_CONTEXT_REMOVE_MESSAGE) return []
  const rawIds = Array.isArray(message.ids) ? message.ids : [message.id]
  return rawIds
    .map((id) => String(id || '').trim())
    .filter(Boolean)
}
