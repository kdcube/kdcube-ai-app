import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  mergeSceneContextDropTargets,
  normalizeSceneContextDropTarget,
  normalizeSceneContextDropTargets,
  sceneContextDropTargetsFromConfig,
} from '../dist/scene/index.js'

test('extracts context drop targets from active profile config', () => {
  const config = {
    contextDropTargets: {
      chat: {
        surfaceRef: 'website.chat',
        railId: 'chat',
        acceptsRootNamespaces: ['*'],
        dropEffect: 'attach',
        delivery: 'chat.attach',
      },
    },
  }

  assert.deepEqual(Object.keys(sceneContextDropTargetsFromConfig(config)), ['chat'])
})

test('merges scene-level and profile-level target overrides', () => {
  const merged = mergeSceneContextDropTargets(
    {
      task_list: {
        surfaceRef: 'website.task_list',
        railId: 'task_list',
        acceptsRootNamespaces: ['task'],
        dropEffect: 'open',
        targetSurface: 'task_tracker.issue_list',
        delivery: 'task.open',
      },
      memories: {
        surfaceRef: 'website.memories',
        railId: 'memories',
        acceptsRootNamespaces: ['mem'],
        dropEffect: 'open',
        targetSurface: 'sdk.memory.viewer',
      },
    },
    {
      task_list: {
        label: 'Open issue',
      },
      memories: false,
    },
  )

  assert.equal(merged.task_list.surfaceRef, 'website.task_list')
  assert.equal(merged.task_list.label, 'Open issue')
  assert.equal(merged.memories, false)
})

test('normalizes target config and accepts aliases', () => {
  const result = normalizeSceneContextDropTarget('pinboard', {
    surfaceRef: 'website.pinboard',
    railId: 'pinboard',
    accepts: '*',
    dropEffect: 'pin',
    delivery: 'pinboard.pin',
  }, {
    knownDeliveries: ['pinboard.pin'],
  })

  assert.equal(result.issue, null)
  assert.equal(result.target?.key, 'pinboard')
  assert.deepEqual(result.target?.acceptsRootNamespaces, ['*'])
  assert.equal(result.target?.delivery, 'pinboard.pin')
})

test('reports invalid delivery and missing open route', () => {
  assert.equal(
    normalizeSceneContextDropTarget('chat', {
      surfaceRef: 'website.chat',
      railId: 'chat',
      acceptsRootNamespaces: ['*'],
      dropEffect: 'attach',
      delivery: 'unknown.attach',
    }, {
      knownDeliveries: ['chat.attach'],
    }).issue?.code,
    'delivery_unknown',
  )

  assert.equal(
    normalizeSceneContextDropTarget('viewer', {
      surfaceRef: 'website.viewer',
      railId: 'viewer',
      acceptsRootNamespaces: ['mem'],
      dropEffect: 'open',
    }).issue?.code,
    'open_route_missing',
  )
})

test('normalizes a target map and omits disabled targets from issues', () => {
  const result = normalizeSceneContextDropTargets({
    contextDropTargets: {
      chat: {
        surfaceRef: 'website.chat',
        railId: 'chat',
        acceptsRootNamespaces: ['*'],
        dropEffect: 'attach',
        delivery: 'chat.attach',
      },
      disabled: false,
    },
  }, {
    knownDeliveries: ['chat.attach'],
  })

  assert.deepEqual(Object.keys(result.targets), ['chat'])
  assert.deepEqual(result.issues, [])
})
