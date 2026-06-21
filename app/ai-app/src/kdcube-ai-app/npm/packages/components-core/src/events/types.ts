export type EventRecord = Record<string, unknown>

export type ComponentEventTransportMode = 'scene' | 'sse' | 'none' | string

export interface ComponentEventSubscriptionClaim {
  id: string
  source?: string
  events?: string[]
  channels?: string[]
  forwardType?: string
  reason?: string
  includeEnvelope?: boolean
  debounceMs?: number
  forward?: EventRecord
}

export interface ComponentEventSubscriptionRequest {
  component: string
  alias?: string
  subscriptions: ComponentEventSubscriptionClaim[]
}

export interface ComponentEventTransport {
  readonly mode: string
  subscribe: (request: ComponentEventSubscriptionRequest) => () => void
}

export interface ComponentEventClientOptions {
  component: string
  alias?: string
  transportMode?: ComponentEventTransportMode
  transports?: Record<string, ComponentEventTransport | undefined>
  logger?: Pick<Console, 'info' | 'warn' | 'debug'>
}

export interface ComponentEventClient {
  readonly component: string
  readonly alias?: string
  readonly transportMode: string
  subscribe: (subscriptions: ComponentEventSubscriptionClaim[]) => () => void
}

export interface NormalizedComponentEventSubscriptionClaim extends ComponentEventSubscriptionClaim {
  id: string
  source: string
  events: string[]
  channels: string[]
  includeEnvelope: boolean
}
