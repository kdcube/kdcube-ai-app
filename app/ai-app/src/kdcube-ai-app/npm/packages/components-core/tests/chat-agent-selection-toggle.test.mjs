import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  chatActions,
  chatReducer,
  initialState,
  isToolDisabled,
  mergeSelectionPatches,
  toolGroupState,
  toolTogglePatch,
} from '../dist/chat/index.js'

// The tool-row click pipeline behind the consent banner's "turn off the
// tools" flow: click → toggle patch → optimistic selection state (the ✓)
// → merged persisted payload for agent_selection_update. Pins the pieces
// so a routing/UI change upstream (e.g. the confirm-policy picker) can be
// diagnosed against a known-good core pipeline.

const SLACK_GROUP = {
  alias: 'slack',
  name: 'Slack',
  kind: 'python',
  system: false,
  tools: [
    { name: 'search_slack', description: 'Search messages' },
    { name: 'upload_slack_file', description: 'Upload a file' },
    { name: 'post_slack_message', description: 'Post a message' },
  ],
}

function loadedState() {
  return chatReducer({ ...initialState }, chatActions.capabilitiesLoaded({
    agent: 'main',
    inventory: { skills: [], tools: [SLACK_GROUP], mcp: [], namespaces: [], supported_models: [] },
    disabled: {},
    model: null,
    cachePolicy: null,
    pending: null,
  }))
}

test('a row click produces the tool deny patch and flips the check optimistically', () => {
  const state = loadedState()
  const patch = toolTogglePatch(SLACK_GROUP, state.capabilities.disabled, 'post_slack_message')
  assert.deepEqual(patch, { tools: { slack: ['post_slack_message'] } })

  const next = chatReducer(state, chatActions.capabilitiesPatchApplied(patch))
  assert.equal(isToolDisabled(next.capabilities.disabled, 'slack', 'post_slack_message'), true)
  assert.equal(isToolDisabled(next.capabilities.disabled, 'slack', 'search_slack'), false)
  assert.equal(toolGroupState(SLACK_GROUP, next.capabilities.disabled), 'partial')
})

test('two unticked tools merge into one persisted payload', () => {
  const state = loadedState()
  const first = toolTogglePatch(SLACK_GROUP, state.capabilities.disabled, 'upload_slack_file')
  const afterFirst = chatReducer(state, chatActions.capabilitiesPatchApplied(first))
  const second = toolTogglePatch(SLACK_GROUP, afterFirst.capabilities.disabled, 'post_slack_message')

  const persisted = mergeSelectionPatches(first, second)
  assert.deepEqual(persisted.tools.slack.sort(), ['post_slack_message', 'upload_slack_file'])

  const final = chatReducer(afterFirst, chatActions.capabilitiesPatchApplied(second))
  assert.equal(isToolDisabled(final.capabilities.disabled, 'slack', 'upload_slack_file'), true)
  assert.equal(isToolDisabled(final.capabilities.disabled, 'slack', 'post_slack_message'), true)
  assert.equal(isToolDisabled(final.capabilities.disabled, 'slack', 'search_slack'), false)
})

test('re-clicking a disabled tool re-enables it', () => {
  const state = loadedState()
  const off = chatReducer(state, chatActions.capabilitiesPatchApplied(
    toolTogglePatch(SLACK_GROUP, state.capabilities.disabled, 'post_slack_message'),
  ))
  const on = chatReducer(off, chatActions.capabilitiesPatchApplied(
    toolTogglePatch(SLACK_GROUP, off.capabilities.disabled, 'post_slack_message'),
  ))
  assert.equal(isToolDisabled(on.capabilities.disabled, 'slack', 'post_slack_message'), false)
  assert.equal(toolGroupState(SLACK_GROUP, on.capabilities.disabled), 'on')
})
