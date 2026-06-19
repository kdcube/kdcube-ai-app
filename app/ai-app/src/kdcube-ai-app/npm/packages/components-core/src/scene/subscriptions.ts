import type { SceneRecord } from './types'

export const SCENE_SUBSCRIBE_MESSAGE = 'kdcube-scene-subscribe'
export const SCENE_UNSUBSCRIBE_MESSAGE = 'kdcube-scene-unsubscribe'
export const SCENE_EVENT_MESSAGE = 'kdcube-scene-event'

export interface SceneEventSubscriptionClaim {
  id: string
  source?: string
  /**
   * Canonical event identities from the backend envelope. These are payload
   * values, so namespace-shaped names such as `task:event:task-changed` are
   * allowed here.
   */
  events?: string[]
  channels?: string[]
  /**
   * Browser transport alias delivered as postMessage.type. Keep this dash-case;
   * the canonical identity is still available in message.scene_event.type.
   */
  forwardType?: string
  reason?: string
  includeEnvelope?: boolean
  debounceMs?: number
  forward?: SceneRecord
}

export interface SceneSubscriptionMessage {
  type: typeof SCENE_SUBSCRIBE_MESSAGE
  widget: string
  alias?: string
  subscriptions: SceneEventSubscriptionClaim[]
}

export interface SceneUnsubscribeMessage {
  type: typeof SCENE_UNSUBSCRIBE_MESSAGE
  widget: string
  alias?: string
}

export interface SceneSubscriptionPostTarget {
  postMessage: (message: unknown, targetOrigin: string) => void
}

export interface PostSceneSubscriptionOptions {
  widget: string
  alias?: string
  subscriptions: SceneEventSubscriptionClaim[]
  target?: SceneSubscriptionPostTarget | null
  origin?: string
}

export interface PostSceneUnsubscribeOptions {
  widget: string
  alias?: string
  target?: SceneSubscriptionPostTarget | null
  origin?: string
}

function parentTarget(): SceneSubscriptionPostTarget | null {
  if (typeof window === 'undefined') return null
  if (!window.parent || window.parent === window) return null
  return window.parent
}

function targetOrigin(origin?: string): string {
  const value = String(origin || '*').trim()
  return value || '*'
}

function cleanSubscription(raw: SceneEventSubscriptionClaim): SceneEventSubscriptionClaim | null {
  const id = String(raw.id || '').trim()
  if (!id) return null
  const events = Array.isArray(raw.events) ? raw.events.map((item) => String(item || '').trim()).filter(Boolean) : []
  const channels = Array.isArray(raw.channels) ? raw.channels.map((item) => String(item || '').trim()).filter(Boolean) : []
  if (!events.length && !channels.length) return null
  const source = raw.source == null ? 'sse' : String(raw.source || '').trim()
  const forwardType = raw.forwardType == null ? undefined : String(raw.forwardType || '').trim()
  const reason = raw.reason == null ? undefined : String(raw.reason || '').trim()
  const debounceMs = Number(raw.debounceMs || 0)
  return {
    id,
    source: source || 'sse',
    events,
    channels,
    forwardType: forwardType || undefined,
    reason: reason || undefined,
    includeEnvelope: Boolean(raw.includeEnvelope),
    debounceMs: Number.isFinite(debounceMs) && debounceMs > 0 ? debounceMs : undefined,
    forward: raw.forward,
  }
}

function cleanSubscriptions(subscriptions: SceneEventSubscriptionClaim[]): SceneEventSubscriptionClaim[] {
  return subscriptions.map(cleanSubscription).filter((item): item is SceneEventSubscriptionClaim => item !== null)
}

export function buildSceneSubscriptionMessage(options: PostSceneSubscriptionOptions): SceneSubscriptionMessage | null {
  const widget = String(options.widget || '').trim()
  if (!widget) return null
  const subscriptions = cleanSubscriptions(Array.isArray(options.subscriptions) ? options.subscriptions : [])
  if (!subscriptions.length) return null
  const alias = options.alias == null ? undefined : String(options.alias || '').trim()
  return {
    type: SCENE_SUBSCRIBE_MESSAGE,
    widget,
    alias: alias || undefined,
    subscriptions,
  }
}

export function buildSceneUnsubscribeMessage(options: PostSceneUnsubscribeOptions): SceneUnsubscribeMessage | null {
  const widget = String(options.widget || '').trim()
  if (!widget) return null
  const alias = options.alias == null ? undefined : String(options.alias || '').trim()
  return {
    type: SCENE_UNSUBSCRIBE_MESSAGE,
    widget,
    alias: alias || undefined,
  }
}

export function postSceneSubscriptions(options: PostSceneSubscriptionOptions): boolean {
  const message = buildSceneSubscriptionMessage(options)
  if (!message) return false
  const target = options.target ?? parentTarget()
  if (!target) return false
  target.postMessage(message, targetOrigin(options.origin))
  return true
}

export function postSceneUnsubscribe(options: PostSceneUnsubscribeOptions): boolean {
  const message = buildSceneUnsubscribeMessage(options)
  if (!message) return false
  const target = options.target ?? parentTarget()
  if (!target) return false
  target.postMessage(message, targetOrigin(options.origin))
  return true
}

export function bindSceneSubscriptions(options: PostSceneSubscriptionOptions): () => boolean {
  postSceneSubscriptions(options)
  return () => postSceneUnsubscribe({
    widget: options.widget,
    alias: options.alias,
    target: options.target,
    origin: options.origin,
  })
}
