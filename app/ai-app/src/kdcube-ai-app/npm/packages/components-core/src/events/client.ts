import {
  normalizeComponentEventSubscriptionClaims,
  normalizeEventTransportMode,
} from './claims'
import type {
  ComponentEventClient,
  ComponentEventClientOptions,
  ComponentEventSubscriptionClaim,
} from './types'

function noop(): void {}

export function createComponentEventClient(options: ComponentEventClientOptions): ComponentEventClient {
  const component = String(options.component || '').trim()
  const alias = options.alias == null ? undefined : String(options.alias || '').trim() || undefined
  const transportMode = normalizeEventTransportMode(options.transportMode, 'none')
  const logger = options.logger

  return {
    component,
    alias,
    transportMode,
    subscribe(subscriptions: ComponentEventSubscriptionClaim[]): () => void {
      if (!component) {
        logger?.warn?.('[kdcube.events] subscription skipped: component missing')
        return noop
      }
      const claims = normalizeComponentEventSubscriptionClaims(subscriptions)
      if (!claims.length) {
        logger?.debug?.('[kdcube.events] subscription skipped: no claims', { component, alias })
        return noop
      }
      if (transportMode === 'none') {
        logger?.info?.('[kdcube.events] subscription disabled by transport', {
          component,
          alias,
          transportMode,
          subscriptions: claims.map((claim) => claim.id),
        })
        return noop
      }
      const transport = options.transports?.[transportMode]
      if (!transport) {
        logger?.warn?.('[kdcube.events] subscription skipped: transport unavailable', {
          component,
          alias,
          transportMode,
          subscriptions: claims.map((claim) => claim.id),
        })
        return noop
      }
      logger?.info?.('[kdcube.events] subscription declared', {
        component,
        alias,
        transportMode,
        subscriptions: claims.map((claim) => claim.id),
      })
      return transport.subscribe({
        component,
        alias,
        subscriptions: claims,
      })
    },
  }
}

export function bindComponentEventSubscriptions(
  options: ComponentEventClientOptions & { subscriptions: ComponentEventSubscriptionClaim[] },
): () => void {
  return createComponentEventClient(options).subscribe(options.subscriptions)
}
