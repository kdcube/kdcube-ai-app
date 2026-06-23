import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  createContextDragBroker,
  normalizeContextDragMessage,
  sceneMatchObjectSelector,
} from '../dist/scene/index.js'

test('normalizes canonical context drag messages', () => {
  const active = normalizeContextDragMessage({
    type: 'kdcube-context-drag-start',
    source_surface_ref: 'chat',
    contexts: [
      {
        ref: 'task:issue:T-1',
        label: 'Task one',
      },
    ],
  })

  assert.equal(active.sourceSurfaceRef, 'chat')
  assert.equal(active.contexts[0].ref, 'task:issue:T-1')
  assert.equal(active.contexts[0].object_ref, 'task:issue:T-1')
})

test('rejects non-canonical drag start messages', () => {
  assert.equal(normalizeContextDragMessage({ type: 'not-canonical-drag-start', contexts: [{ ref: 'task:issue:T-1' }] }), null)
})

test('matches drop targets by selector policy', () => {
  const broker = createContextDragBroker({
    objectAction: async () => ({ ok: true }),
    dispatchOpenResponse: () => ({ ok: true, code: 'dispatched', targetSurface: 'task.issue', message: 'ok' }),
  })
  broker.handleDragStart({
    type: 'kdcube-context-drag-start',
    contexts: [{ ref: 'task:attachment:T-1/file', namespace: 'task:attachment' }],
  })

  assert.equal(sceneMatchObjectSelector('task:attachment:T-1/file', 'task:*'), true)
  assert.equal(sceneMatchObjectSelector('task:attachment:T-1/file', 'task:issue:*'), false)
  assert.equal(broker.accepts({ surfaceRef: 'tasks', targetSurface: 'task.issue', accepts: { open: ['task:*'] } }), true)
  assert.equal(broker.accepts({ surfaceRef: 'memory', targetSurface: 'memory.viewer', accepts: { open: ['mem:*'] } }), false)
})

test('opens owning surfaces through provider object action', async () => {
  const calls = []
  const broker = createContextDragBroker({
    objectAction: async (request) => {
      calls.push(request)
      return {
        ok: true,
        object_ref: request.object_ref,
        ui_event: {
          target_surface: request.target_surface,
          object_ref: request.object_ref,
        },
      }
    },
    dispatchOpenResponse: (response, source) => ({
      ok: true,
      code: 'dispatched',
      targetSurface: response.ui_event.target_surface,
      message: `opened ${source.ref}`,
    }),
  })
  broker.handleDragStart({
    type: 'kdcube-context-drag-start',
    contexts: [{ ref: 'mem:record:mem_1', label: 'Memory' }],
  })

  const result = await broker.dropOnTarget({
    surfaceRef: 'memories',
    targetSurface: 'sdk.memory.viewer',
    accepts: { open: ['mem:*'] },
    dropEffect: 'open',
  })

  assert.equal(result.ok, true)
  assert.equal(result.code, 'opened')
  assert.equal(calls[0].object_ref, 'mem:record:mem_1')
  assert.equal(calls[0].target_surface, 'sdk.memory.viewer')
})

test('delivers pin and attach targets locally without provider open', async () => {
  const delivered = []
  const broker = createContextDragBroker({
    objectAction: async () => {
      throw new Error('provider should not be called for pin target')
    },
    dispatchOpenResponse: () => ({ ok: true, code: 'dispatched', targetSurface: 'unused', message: 'unused' }),
  })
  broker.handleDragStart({
    type: 'kdcube-context-drag-start',
    contexts: [{ ref: 'task:issue:T-1' }],
  })

  const result = await broker.dropOnTarget({
    surfaceRef: 'pinboard',
    targetSurface: 'canvas.main',
    accepts: { pin: ['*'] },
    dropEffect: 'pin',
    deliverContext: ({ context, target }) => delivered.push([context.ref, target.surfaceRef]),
  })

  assert.equal(result.ok, true)
  assert.deepEqual(delivered, [['task:issue:T-1', 'pinboard']])
})
