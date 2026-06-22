import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  canvasFromPatchEvent,
  canvasFromReadResponse,
  emptyCanvasDefinition,
  upsertCanvasDefinition,
} from '../dist/canvas/index.js'

test('upsertCanvasDefinition dedupes boards by name and prefers canonical ids', () => {
  const boards = [
    emptyCanvasDefinition('main'),
    { ...emptyCanvasDefinition('main'), id: 'cnv:user:main', revision: 2, cards: [] },
    emptyCanvasDefinition('demo-board'),
  ].reduce((current, board) => upsertCanvasDefinition(current, board), [])

  assert.deepEqual(boards.map((board) => board.name), ['main', 'demo-board'])
  assert.equal(boards.find((board) => board.name === 'main')?.id, 'cnv:user:main')
})

test('canvasFromPatchEvent preserves comment bodies and counts', () => {
  const canvas = canvasFromPatchEvent({
    type: 'canvas.patch.applied',
    canvas_name: 'main',
    canvas_id: 'cnv:user:main',
    revision: 3,
    changed_cards: [
      {
        id: 'O7',
        kind: 'conversation',
        title: 'Membership Cancellation Inquiry',
        logical_path: 'conv:demo/main/abc',
        rect: { x: 20, y: 30, w: 240, h: 120 },
        comments: [{ id: 'comment_1', text: 'visible comment', actor: 'agent', created_at: 1782086400 }],
      },
    ],
  })

  assert.equal(canvas.cards[0].commentsCount, 1)
  assert.deepEqual(canvas.cards[0].comments, [
    { id: 'comment_1', text: 'visible comment', actor: 'agent', createdAt: 1782086400 },
  ])
})

test('canvasFromReadResponse carries raw canvas comments alongside projection rows', () => {
  const canvas = canvasFromReadResponse({
    canvas_id: 'cnv:user:main',
    canvas_name: 'main',
    revision: 4,
    canvas: {
      cards: [
        {
          id: 'O7',
          comments: [{ id: 'comment_2', text: 'comment from full read', actor: 'user' }],
        },
      ],
    },
    projection: {
      schema: 'kdcube.canvas.projection.v1',
      cards_count: 1,
      legend: [
        {
          id: 'O7',
          kind: 'conversation',
          title: 'Membership Cancellation Inquiry',
          logical_path: 'conv:demo/main/abc',
          rect: { x: 20, y: 30, w: 240, h: 120 },
          comments_count: 1,
        },
      ],
    },
  })

  assert.equal(canvas.cards[0].commentsCount, 1)
  assert.equal(canvas.cards[0].comments?.[0]?.text, 'comment from full read')
})
