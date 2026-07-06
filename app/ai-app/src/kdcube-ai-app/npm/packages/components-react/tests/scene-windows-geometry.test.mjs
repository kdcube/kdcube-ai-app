import assert from 'node:assert/strict'
import { test } from 'node:test'
import { rectsIntersect, buriedAliases, windowRectFromState } from '../dist/scene/index.js'

const win = (over) => ({ open: true, expanded: false, floating: true, x: 0, y: 0, w: 100, h: 100, z: 1, everOpened: true, ...over })

test('overlap-based buried detection: higher-z intersecting window buries a lower one', () => {
  const wins = {
    chat: win({ x: 100, y: 100, w: 400, h: 400, z: 10, floating: false }),
    memories: win({ x: 300, y: 200, w: 300, h: 300, z: 20 }),
    tasks: win({ x: 900, y: 100, w: 200, h: 200, z: 30 }),
  }
  const rectOf = (alias, state) => (alias === 'chat'
    ? { left: 100, top: 100, right: 500, bottom: 500 } // docked tile rect
    : windowRectFromState(state))
  const buried = buriedAliases(wins, rectOf)
  assert.deepEqual([...buried].sort(), ['chat'])
})

test('closed windows and non-overlapping higher-z windows bury nothing', () => {
  const wins = {
    a: win({ z: 10 }),
    b: win({ x: 500, y: 500, z: 20 }),
    c: win({ x: 10, y: 10, z: 30, open: false }),
  }
  const buried = buriedAliases(wins, (_, s) => windowRectFromState(s))
  assert.equal(buried.size, 0)
  assert.equal(rectsIntersect({ left: 0, top: 0, right: 10, bottom: 10 }, { left: 10, top: 0, right: 20, bottom: 10 }), false)
})
