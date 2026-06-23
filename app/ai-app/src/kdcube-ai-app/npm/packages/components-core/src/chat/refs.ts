/**
 * Pure object-ref helpers used by the reducers.
 *
 * The widget split these across `features/chat/fileDrag.ts` (which also holds
 * view-only drag-data helpers that depend on a configurable canvas-ingress
 * message type) and `features/chat/historicalRefs.ts`. Only the pure, config-free
 * helpers belong in the headless engine; the drag-data builders stay in the view.
 */

const NAMESPACE_REF = /^[a-z][a-z0-9_.-]*:/i
const BROWSER_SCHEMES = new Set(['blob:', 'data:', 'http:', 'https:', 'javascript:', 'mailto:'])
const DURABLE_FI_REF = /^fi:conv_[^.]+\.turn_[^.]+\./

export function canonicalObjectRef(...refs: Array<string | null | undefined>): string {
  for (const raw of refs) {
    const ref = typeof raw === 'string' ? raw.trim() : ''
    if (!ref) continue
    const scheme = (ref.match(NAMESPACE_REF)?.[0] || '').toLowerCase()
    if (scheme && !BROWSER_SCHEMES.has(scheme)) return ref
  }
  return ''
}

/** The leading namespace token of an object ref (`task:issue:1` → `task`), or "". */
export function namespaceFromObjectRef(ref: string): string {
  const match = String(ref || '').trim().match(/^([a-z][a-z0-9_.-]*):/i)
  return match?.[1]?.toLowerCase() || ''
}

export function isDurableFiRef(ref: string): boolean {
  return DURABLE_FI_REF.test(String(ref || '').trim())
}

export function isDirectDownloadObjectRef(ref: string): boolean {
  return isDurableFiRef(ref)
}

export function durableHistoricalObjectRef(value: unknown, conversationId?: string): string | null {
  const ref = typeof value === 'string' ? value.trim() : ''
  if (!ref) return null
  const conv = String(conversationId || '').trim()
  if (ref.startsWith('fi:turn_') && conv && !/[./\\]/.test(conv)) {
    return `fi:conv_${conv}.${ref.slice('fi:'.length)}`
  }
  return ref
}
