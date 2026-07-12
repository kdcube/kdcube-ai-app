import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  applySelectionPatch,
  chatActions,
  chatReducer,
  initialState,
  isSubagentsDisabled,
  mergeSelectionPatches,
  subagentLaneEventKind,
  subagentStampOf,
  subagentThreadsForTurn,
  subagentsTogglePatch,
} from '../dist/chat/index.js'

// ReAct subagents v2, client half: stamped child-conversation emissions
// multiplex into threads keyed by child conversation id (same reducer
// pipeline as the main lane, nested turn list), lane events drive the
// thread's status/milestones, and reload rebuilds the same threads from the
// parent turns' `forks` descriptors. Plus the helper-agents deny-key
// selection logic the picker toggle rides.

const STAMP = {
  child_conversation_id: 'conv_child_a',
  forked_from_conversation_id: 'conv_parent',
  forked_from_turn_id: 'turn_p1',
  charter_goal: 'Research the market',
}

function envelope({ type = 'chat.delta', stamp = STAMP, turnId = 'turn_c1', data = {}, delta, event } = {}) {
  return {
    type,
    timestamp: '2026-07-12T10:00:00Z',
    service: { request_id: 'req1' },
    conversation: { session_id: '', conversation_id: stamp?.child_conversation_id || 'conv_child_a', turn_id: turnId },
    event: event || { step: 'react', status: 'running' },
    data,
    ...(delta ? { delta, extra: {} } : {}),
    ...(stamp ? { subagent: stamp } : {}),
  }
}

function parentState() {
  return { ...initialState, conversationId: 'conv_parent' }
}

test('the stamp discriminates subagent traffic; main-lane envelopes carry none', () => {
  const stamped = envelope({ delta: { text: 'hi', marker: 'answer', index: 0 } })
  assert.equal(subagentStampOf(stamped).child_conversation_id, 'conv_child_a')
  const plain = envelope({ stamp: null, delta: { text: 'hi', marker: 'answer', index: 0 } })
  assert.equal(subagentStampOf(plain), null)
})

test('a stamped delta builds the thread with the SAME answer pipeline; main turns stay untouched', () => {
  let state = parentState()
  state = chatReducer(state, chatActions.subagentStreamEvent({
    kind: 'delta',
    envelope: envelope({ delta: { text: 'Part one ', marker: 'answer', index: 0 } }),
  }))
  state = chatReducer(state, chatActions.subagentStreamEvent({
    kind: 'delta',
    envelope: envelope({ delta: { text: 'part two.', marker: 'answer', index: 1 } }),
  }))
  const thread = state.threads.conv_child_a
  assert.ok(thread, 'thread keyed by child conversation id')
  assert.equal(thread.parentTurnId, 'turn_p1')
  assert.equal(thread.charterGoal, 'Research the market')
  assert.equal(thread.status, 'running')
  assert.equal(thread.hydration, 'live')
  assert.equal(thread.turns.length, 1)
  assert.equal(thread.turns[0].id, 'turn_c1')
  assert.equal(thread.turns[0].answer, 'Part one part two.')
  assert.equal(state.turns.length, 0, 'no phantom turn on the main lane')
})

test("another conversation's stamped traffic is dropped", () => {
  const foreign = { ...STAMP, forked_from_conversation_id: 'conv_other' }
  const state = chatReducer(parentState(), chatActions.subagentStreamEvent({
    kind: 'delta',
    envelope: envelope({ stamp: foreign, delta: { text: 'x', marker: 'answer', index: 0 } }),
  }))
  assert.deepEqual(state.threads, {})
})

test('fan-out: concurrent children anchor as separate threads under the fork turn, in fork order', () => {
  let state = parentState()
  const stampB = { ...STAMP, child_conversation_id: 'conv_child_b', charter_goal: 'Draft the summary' }
  state = chatReducer(state, chatActions.subagentStreamEvent({
    kind: 'start',
    envelope: envelope({ type: 'chat.start', data: { message: '' } }),
  }))
  state = chatReducer(state, chatActions.subagentStreamEvent({
    kind: 'start',
    envelope: { ...envelope({ type: 'chat.start', stamp: stampB, turnId: 'turn_c2', data: { message: '' } }), timestamp: '2026-07-12T10:00:05Z' },
  }))
  assert.equal(Object.keys(state.threads).length, 2)
  const anchored = subagentThreadsForTurn(state.threads, 'turn_p1')
  assert.deepEqual(anchored.map((t) => t.childConversationId), ['conv_child_a', 'conv_child_b'])
  assert.deepEqual(subagentThreadsForTurn(state.threads, 'turn_p9'), [])
})

test('lane events drive status and milestones: charter/contribution/converged/failed', () => {
  assert.equal(subagentLaneEventKind(envelope({ data: { event: { type: 'subagent.contribution' } } })), 'contribution')
  assert.equal(subagentLaneEventKind(envelope({ type: 'subagent.converged' })), 'converged')

  let state = parentState()
  state = chatReducer(state, chatActions.subagentStreamEvent({
    kind: 'step',
    envelope: envelope({ data: { event: { type: 'subagent.charter' }, text: 'Research the market' } }),
  }))
  assert.equal(state.threads.conv_child_a.status, 'running')

  state = chatReducer(state, chatActions.subagentStreamEvent({
    kind: 'step',
    envelope: envelope({ data: { event: { type: 'subagent.contribution' }, text: 'Found three sources', refs: ['conv:fi:conv_child_a.turn_c1/f.md'] } }),
  }))
  assert.equal(state.threads.conv_child_a.contributions.length, 1)
  assert.equal(state.threads.conv_child_a.contributions[0].text, 'Found three sources')
  assert.deepEqual(state.threads.conv_child_a.contributions[0].refs, ['conv:fi:conv_child_a.turn_c1/f.md'])

  state = chatReducer(state, chatActions.subagentStreamEvent({
    kind: 'step',
    envelope: envelope({ data: { event: { type: 'subagent.converged' }, text: 'Charter completed.' } }),
  }))
  assert.equal(state.threads.conv_child_a.status, 'converged')
  assert.equal(state.threads.conv_child_a.statusDetail, 'Charter completed.')

  const failed = chatReducer(parentState(), chatActions.subagentStreamEvent({
    kind: 'step',
    envelope: envelope({ data: { event: { type: 'subagent.failed' }, reason: 'budget exhausted' } }),
  }))
  assert.equal(failed.threads.conv_child_a.status, 'failed')
  assert.equal(failed.threads.conv_child_a.statusDetail, 'budget exhausted')
})

const PARENT_CONVERSATION = {
  conversation_id: 'conv_parent',
  conversation_title: 'Market work',
  turns: [
    {
      turn_id: 'turn_p1',
      artifacts: [
        { type: 'chat:user', ts: '2026-07-12T09:00:00Z', data: { text: 'research this' } },
      ],
      forks: [
        { child_conversation_id: 'conv_child_a', charter_goal: 'Research the market', forked_at: '2026-07-12T09:01:00Z' },
        { child_conversation_id: 'conv_child_b', charter_goal: 'Draft the summary', forked_at: '2026-07-12T09:02:00Z' },
      ],
    },
    {
      turn_id: 'turn_p2',
      artifacts: [
        {
          type: 'artifact:conv.artifacts.events',
          ts: '2026-07-12T09:10:00Z',
          data: {
            payload: {
              items: [
                {
                  type: 'external_event',
                  event: { type: 'subagent.converged' },
                  data: { child_conversation_id: 'conv_child_a', text: 'Completed the charter.' },
                },
              ],
            },
          },
        },
      ],
    },
  ],
}

test('reload: `forks` descriptors become collapsed stubs at their turns; stored completions fold status', () => {
  const state = chatReducer({ ...initialState }, chatActions.hydrateConversation({ conversation: PARENT_CONVERSATION }))
  const threadA = state.threads.conv_child_a
  const threadB = state.threads.conv_child_b
  assert.ok(threadA && threadB)
  assert.equal(threadA.hydration, 'stub')
  assert.equal(threadA.parentTurnId, 'turn_p1')
  assert.equal(threadA.charterGoal, 'Research the market')
  assert.equal(threadA.status, 'converged', 'terminal event stored on a later turn folds into the stub')
  assert.equal(threadA.statusDetail, 'Completed the charter.')
  assert.equal(threadB.status, 'unknown', 'no stored completion -> no guessed status')
  assert.equal(threadA.turns.length, 0, 'collapsed stub carries no turns until expanded')
})

test('expanding a stub hydrates the fetched child conversation through the same historical pipeline', () => {
  let state = chatReducer({ ...initialState }, chatActions.hydrateConversation({ conversation: PARENT_CONVERSATION }))
  state = chatReducer(state, chatActions.subagentThreadLoading('conv_child_a'))
  assert.equal(state.threads.conv_child_a.hydration, 'loading')
  state = chatReducer(state, chatActions.subagentThreadHydrated({
    childConversationId: 'conv_child_a',
    conversation: {
      conversation_id: 'conv_child_a',
      forked_from: { conversation_id: 'conv_parent', turn_id: 'turn_p1' },
      turns: [
        {
          turn_id: 'turn_c1',
          artifacts: [
            { type: 'chat:assistant', ts: '2026-07-12T09:05:00Z', data: { text: 'Here are the findings.' } },
          ],
        },
      ],
    },
  }))
  const thread = state.threads.conv_child_a
  assert.equal(thread.hydration, 'ready')
  assert.equal(thread.turns.length, 1)
  assert.equal(thread.turns[0].answer, 'Here are the findings.')
  // a failed fetch is retryable state, not a lost thread
  const errored = chatReducer(state, chatActions.subagentThreadLoadError({
    childConversationId: 'conv_child_b',
    error: 'fetch failed',
  }))
  assert.equal(errored.threads.conv_child_b.hydration, 'error')
  assert.equal(errored.threads.conv_child_b.hydrationError, 'fetch failed')
})

test('threads reset on conversation switch', () => {
  let state = chatReducer({ ...initialState }, chatActions.hydrateConversation({ conversation: PARENT_CONVERSATION }))
  assert.equal(Object.keys(state.threads).length, 2)
  state = chatReducer(state, chatActions.startNewConversation())
  assert.deepEqual(state.threads, {})
})

test('helper-agents deny key: toggle patch, optimistic flip, merge, and re-enable', () => {
  // offered + untouched -> on; the toggle produces the deny patch
  assert.equal(isSubagentsDisabled({}), false)
  assert.deepEqual(subagentsTogglePatch({}), { subagents: true })
  // optimistic flip mirrors the server merge
  const off = applySelectionPatch({}, { subagents: true })
  assert.deepEqual(off, { subagents: true })
  assert.equal(isSubagentsDisabled(off), true)
  // re-enable clears the stored key entirely
  const on = applySelectionPatch(off, subagentsTogglePatch(off))
  assert.deepEqual(on, {})
  // debounced saves merge; later toggle wins; other categories ride along
  const merged = mergeSelectionPatches({ subagents: true, skills: { s1: true } }, { subagents: false })
  assert.deepEqual(merged, { skills: { s1: true }, subagents: false })
  // the persisted body is the patch minus the model pick — the deny key rides
  // `disabled` exactly like the other categories
  const { model, ...disabled } = { ...merged, model: null }
  assert.equal(model, null)
  assert.deepEqual(disabled, { skills: { s1: true }, subagents: false })
})
