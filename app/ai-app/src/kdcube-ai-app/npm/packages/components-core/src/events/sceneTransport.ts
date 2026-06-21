import { normalizeComponentEventSubscriptionClaims } from './claims'
import type {
  ComponentEventSubscriptionClaim,
  ComponentEventSubscriptionRequest,
  ComponentEventTransport,
  EventRecord,
} from './types'

export const SCENE_SUBSCRIBE_MESSAGE = 'kdcube-scene-subscribe'
export const SCENE_UNSUBSCRIBE_MESSAGE = 'kdcube-scene-unsubscribe'
export const SCENE_EVENT_MESSAGE = 'kdcube-scene-event'

export interface SceneSubscriptionMessage {
  type: typeof SCENE_SUBSCRIBE_MESSAGE
  widget: string
  alias?: string
  subscriptions: ComponentEventSubscriptionClaim[]
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
  subscriptions: ComponentEventSubscriptionClaim[]
  target?: SceneSubscriptionPostTarget | null
  origin?: string
}

export interface PostSceneUnsubscribeOptions {
  widget: string
  alias?: string
  target?: SceneSubscriptionPostTarget | null
  origin?: string
}

export interface SceneEventTransportOptions {
  target?: SceneSubscriptionPostTarget | null
  origin?: string
  logger?: Pick<Console, 'info' | 'warn'>
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

export function buildSceneSubscriptionMessage(options: PostSceneSubscriptionOptions): SceneSubscriptionMessage | null {
  const widget = String(options.widget || '').trim()
  if (!widget) return null
  const subscriptions = normalizeComponentEventSubscriptionClaims(Array.isArray(options.subscriptions) ? options.subscriptions : [])
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

export function createSceneEventTransport(options: SceneEventTransportOptions = {}): ComponentEventTransport {
  return {
    mode: 'scene',
    subscribe(request: ComponentEventSubscriptionRequest): () => void {
      const widget = request.alias || request.component
      const unsubscribe = bindSceneSubscriptions({
        widget,
        alias: request.alias,
        subscriptions: request.subscriptions,
        target: options.target,
        origin: options.origin,
      })
      options.logger?.info?.('[kdcube.events] scene transport subscription sent', {
        component: request.component,
        alias: request.alias,
        widget,
        subscriptions: request.subscriptions.map((claim) => claim.id),
      })
      return () => {
        const ok = unsubscribe()
        options.logger?.info?.('[kdcube.events] scene transport unsubscribe sent', {
          component: request.component,
          alias: request.alias,
          widget,
          ok,
        })
      }
    },
  }
}

export function sceneEventForwardMessage(type: string, data: EventRecord = {}): EventRecord {
  return {
    ...data,
    type: type || SCENE_EVENT_MESSAGE,
  }
}
