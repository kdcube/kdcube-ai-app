import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  applyChatStep,
  createEmptyTurn,
  hydrateHistoricalConversation,
  initialState,
} from '../dist/chat/index.js'

function accountingEnvelope(conversationId, turnId, cost = 0.25) {
  return {
    type: 'accounting.usage',
    timestamp: '2026-06-17T23:20:00.000Z',
    service: { request_id: `req:${turnId}` },
    conversation: {
      session_id: 'session-1',
      conversation_id: conversationId,
      turn_id: turnId,
    },
    event: {
      step: 'accounting',
      status: 'completed',
      title: 'Turn Cost',
      agent: null,
    },
    data: {
      cost_total_usd: cost,
    },
  }
}

test('ignores accounting usage events outside the active chat turn', () => {
  const state = {
    ...initialState,
    conversationId: 'conv-1',
    turns: [createEmptyTurn('turn-1', 1_000, 'hello')],
  }

  const next = applyChatStep(
    state,
    accountingEnvelope('canvas_pins_search_123', 'canvas_pins_search_123'),
  )

  assert.equal(next, state)
  assert.equal(next.turns.length, 1)
  assert.equal(next.turns[0].costUsd, null)
  assert.equal(next.turns[0].steps.accounting, undefined)
})

test('accepts accounting usage events for an existing chat turn', () => {
  const state = {
    ...initialState,
    conversationId: 'conv-1',
    turns: [createEmptyTurn('turn-1', 1_000, 'hello')],
  }

  const next = applyChatStep(state, accountingEnvelope('conv-1', 'turn-1', 0.75))

  assert.equal(next.turns.length, 1)
  assert.equal(next.turns[0].costUsd, 0.75)
  assert.equal(next.turns[0].steps.accounting.status, 'completed')
})

test('historical accounting replay keeps only rows scoped to the hydrated turn', () => {
  const turns = hydrateHistoricalConversation({
    conversation_id: 'conv-1',
    turns: [
      {
        turn_id: 'turn-1',
        artifacts: [
          {
            type: 'artifact:conv.artifacts.events',
            ts: '2026-06-17T23:21:00.000Z',
            data: {
              payload: {
                items: [
                  {
                    type: 'accounting.usage',
                    conversation: {
                      conversation_id: 'memory_search_123',
                      turn_id: 'memory_search_123',
                    },
                    data: { cost_total_usd: 99 },
                  },
                  {
                    type: 'accounting.usage',
                    conversation: {
                      conversation_id: 'conv-1',
                      turn_id: 'turn-1',
                    },
                    data: { cost_total_usd: 0.5 },
                  },
                ],
              },
            },
          },
        ],
      },
    ],
  })

  assert.equal(turns.length, 1)
  assert.equal(turns[0].costUsd, 0.5)
})
