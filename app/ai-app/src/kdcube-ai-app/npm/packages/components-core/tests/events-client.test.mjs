import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  bindComponentEventSubscriptions,
  createComponentEventClient,
  createSceneEventTransport,
  normalizeEventTransportMode,
} from '../dist/events/index.js'

function target(messages) {
  return {
    postMessage(message, origin) {
      messages.push({ message, origin })
    },
  }
}

test('normalizes live event transport aliases', () => {
  assert.equal(normalizeEventTransportMode('host'), 'scene')
  assert.equal(normalizeEventTransportMode('widget'), 'sse')
  assert.equal(normalizeEventTransportMode('disabled'), 'none')
  assert.equal(normalizeEventTransportMode('', 'scene'), 'scene')
})

test('scene transport posts component-owned claims', () => {
  const messages = []
  const cleanup = bindComponentEventSubscriptions({
    component: 'usage_card',
    transportMode: 'scene',
    transports: {
      scene: createSceneEventTransport({ target: target(messages), origin: 'https://host.example' }),
    },
    subscriptions: [
      {
        id: 'usage-refresh',
        events: ['accounting.usage'],
        channels: ['chat_service'],
        forward: {
          type: 'kdcube.surface.command',
          target_surface: 'sdk.usage.card',
          action: 'refresh',
        },
      },
    ],
  })

  assert.equal(messages.length, 1)
  assert.equal(messages[0].origin, 'https://host.example')
  assert.equal(messages[0].message.type, 'kdcube-scene-subscribe')
  assert.equal(messages[0].message.widget, 'usage_card')
  assert.equal(messages[0].message.subscriptions[0].id, 'usage-refresh')

  cleanup()
  assert.equal(messages.length, 2)
  assert.equal(messages[1].message.type, 'kdcube-scene-unsubscribe')
})

test('missing transport leaves subscription inert', () => {
  const client = createComponentEventClient({
    component: 'stats',
    transportMode: 'sse',
    transports: {},
  })
  const cleanup = client.subscribe([{ id: 'stats-snapshot', events: ['kdcube.stats.snapshot'] }])
  assert.equal(typeof cleanup, 'function')
  cleanup()
})
