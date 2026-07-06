import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  applySelectionPatch,
  chatActions,
  chatReducer,
  initialState,
  mergeSelectionPatches,
  toolGroupState,
  toolGroupTogglePatch,
  toolTogglePatch,
} from '../dist/chat/index.js'

const webGroup = {
  alias: 'web_tools',
  name: 'web',
  kind: 'python',
  system: false,
  tools: [
    { name: 'web_search', description: 'Search the web.' },
    { name: 'web_fetch', description: 'Fetch a page.' },
  ],
}

test('applySelectionPatch mirrors the server merge semantics', () => {
  let disabled = {}
  disabled = applySelectionPatch(disabled, { tools: { gmail: true } })
  assert.deepEqual(disabled, { tools: { gmail: true } })

  disabled = applySelectionPatch(disabled, { mcp: { knowledge: true }, skills: { 'public.a': true } })
  assert.deepEqual(disabled, { tools: { gmail: true }, mcp: { knowledge: true }, skills: ['public.a'] })

  // false re-enables; other toggles stay.
  disabled = applySelectionPatch(disabled, { tools: { gmail: false }, skills: { 'public.a': false } })
  assert.deepEqual(disabled, { mcp: { knowledge: true } })

  // A name list replaces; an empty list re-enables.
  disabled = applySelectionPatch(disabled, { tools: { web_tools: ['web_search'] } })
  assert.deepEqual(disabled.tools, { web_tools: ['web_search'] })
  disabled = applySelectionPatch(disabled, { tools: { web_tools: [] } })
  assert.equal(disabled.tools, undefined)
})

test('mergeSelectionPatches keeps the latest toggle per key', () => {
  const merged = mergeSelectionPatches(
    { tools: { gmail: true, web_tools: ['web_search'] }, skills: { 'public.a': true } },
    { tools: { gmail: false }, named_services: { task: true }, skills: { 'public.b': true } },
  )
  assert.deepEqual(merged, {
    tools: { gmail: false, web_tools: ['web_search'] },
    named_services: { task: true },
    skills: { 'public.a': true, 'public.b': true },
  })
})

test('tool toggles collapse to minimal group form', () => {
  // Nothing disabled -> disabling one tool stores a name list.
  assert.deepEqual(toolTogglePatch(webGroup, {}, 'web_search'), {
    tools: { web_tools: ['web_search'] },
  })
  // Disabling the last remaining tool collapses to the whole-group form.
  assert.deepEqual(
    toolTogglePatch(webGroup, { tools: { web_tools: ['web_search'] } }, 'web_fetch'),
    { tools: { web_tools: true } },
  )
  // Whole group off; re-enabling one leaves the others in a name list.
  assert.deepEqual(
    toolTogglePatch(webGroup, { tools: { web_tools: true } }, 'web_search'),
    { tools: { web_tools: ['web_fetch'] } },
  )
  // Re-enabling the only disabled tool clears the entry.
  assert.deepEqual(
    toolTogglePatch(webGroup, { tools: { web_tools: ['web_search'] } }, 'web_search'),
    { tools: { web_tools: false } },
  )
})

test('group state and master toggle', () => {
  assert.equal(toolGroupState(webGroup, {}), 'on')
  assert.equal(toolGroupState(webGroup, { tools: { web_tools: true } }), 'off')
  assert.equal(toolGroupState(webGroup, { tools: { web_tools: ['web_search'] } }), 'partial')
  assert.equal(toolGroupState(webGroup, { tools: { web_tools: ['web_search', 'web_fetch'] } }), 'off')
  // System groups are always on regardless of any (clamped-away) record.
  assert.equal(toolGroupState({ ...webGroup, system: true }, { tools: { web_tools: true } }), 'on')

  assert.deepEqual(toolGroupTogglePatch(webGroup, {}), { tools: { web_tools: true } })
  assert.deepEqual(
    toolGroupTogglePatch(webGroup, { tools: { web_tools: ['web_search'] } }),
    { tools: { web_tools: false } },
  )
})

test('capabilities slice: load, optimistic patch, save reconcile', () => {
  assert.deepEqual(initialState.capabilities, {
    status: 'idle',
    error: null,
    agent: null,
    inventory: null,
    disabled: {},
    saving: false,
    saveError: null,
  })

  let state = chatReducer(initialState, chatActions.capabilitiesLoading())
  assert.equal(state.capabilities.status, 'loading')

  const inventory = { agent: 'main', tools: [webGroup], mcp: [], named_services: [], skills: [] }
  state = chatReducer(state, chatActions.capabilitiesLoaded({
    agent: 'main',
    inventory,
    disabled: { mcp: { knowledge: true } },
  }))
  assert.equal(state.capabilities.status, 'ready')
  assert.equal(state.capabilities.agent, 'main')
  assert.deepEqual(state.capabilities.disabled, { mcp: { knowledge: true } })

  state = chatReducer(state, chatActions.capabilitiesPatchApplied({ tools: { web_tools: true } }))
  assert.deepEqual(state.capabilities.disabled, { mcp: { knowledge: true }, tools: { web_tools: true } })

  // Server reconcile wins (e.g. clamped record).
  state = chatReducer(state, chatActions.capabilitiesSelectionSaved({ tools: { web_tools: true } }))
  assert.deepEqual(state.capabilities.disabled, { tools: { web_tools: true } })
  assert.equal(state.capabilities.saving, false)

  state = chatReducer(state, chatActions.capabilitiesSaveError('offline'))
  assert.equal(state.capabilities.saveError, 'offline')
  // The next optimistic toggle clears the stale save error.
  state = chatReducer(state, chatActions.capabilitiesPatchApplied({ tools: { web_tools: false } }))
  assert.equal(state.capabilities.saveError, null)
})

test('capabilities load error is quiet state, not a throw', () => {
  const state = chatReducer(initialState, chatActions.capabilitiesLoadError('boom'))
  assert.equal(state.capabilities.status, 'error')
  assert.equal(state.capabilities.error, 'boom')
})
