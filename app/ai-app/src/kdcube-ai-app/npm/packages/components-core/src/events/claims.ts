import type {
  ComponentEventSubscriptionClaim,
  NormalizedComponentEventSubscriptionClaim,
} from './types'

function cleanText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function cleanList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => cleanText(item)).filter(Boolean)
  }
  const item = cleanText(value)
  return item ? [item] : []
}

export function normalizeEventTransportMode(value: unknown, fallback = 'none'): string {
  const text = cleanText(value).toLowerCase()
  if (text === 'scene' || text === 'host' || text === 'parent') return 'scene'
  if (text === 'sse' || text === 'self' || text === 'widget') return 'sse'
  if (text === 'none' || text === 'off' || text === 'disabled') return 'none'
  return text || fallback
}

export function normalizeComponentEventSubscriptionClaim(
  raw: ComponentEventSubscriptionClaim,
  index = 0,
): NormalizedComponentEventSubscriptionClaim | null {
  if (!raw || typeof raw !== 'object') return null
  const id = cleanText(raw.id) || `subscription-${index}`
  const events = cleanList(raw.events)
  const channels = cleanList(raw.channels)
  if (!events.length && !channels.length) return null
  const source = cleanText(raw.source) || 'sse'
  const forwardType = cleanText(raw.forwardType)
  const reason = cleanText(raw.reason)
  const debounceMs = Number(raw.debounceMs || 0)
  return {
    id,
    source,
    events,
    channels,
    forwardType: forwardType || undefined,
    reason: reason || undefined,
    includeEnvelope: Boolean(raw.includeEnvelope),
    debounceMs: Number.isFinite(debounceMs) && debounceMs > 0 ? debounceMs : undefined,
    forward: raw.forward && typeof raw.forward === 'object' && !Array.isArray(raw.forward)
      ? raw.forward
      : undefined,
  }
}

export function normalizeComponentEventSubscriptionClaims(
  subscriptions: ComponentEventSubscriptionClaim[],
): NormalizedComponentEventSubscriptionClaim[] {
  return (Array.isArray(subscriptions) ? subscriptions : [])
    .map(normalizeComponentEventSubscriptionClaim)
    .filter((item): item is NormalizedComponentEventSubscriptionClaim => item !== null)
}
