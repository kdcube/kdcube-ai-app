import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  chatActions,
  chatReducer,
  initialState,
} from '../../components-core/dist/chat/index.js'

// Internal-realm/config denials with a declared `fix` affordance render an
// actionable card (banner) — the consent card's peer for denials consent
// cannot fix. Regression for the exact surfaced case: a named-service tool
// denial reached chat as a plain error and the agent improvised advice.

function stepEnvelope(data, { turnId = 't1', step = 'tool_result' } = {}) {
  return {
    type: 'chat.step',
    timestamp: new Date().toISOString(),
    conversation: { conversation_id: 'c1', turn_id: turnId },
    event: { step, status: 'error', title: 'tool result' },
    data,
  }
}

const USER_FIX_DENIAL = {
  ok: false,
  error: 'named_service_tool_not_allowed_for_client',
  message: "Client 'main' is not configured to call tool 'get_object' on namespace 'task'.",
  details: { namespace: 'task', tool: 'get_object', client_id: 'main' },
  fix: {
    actor: 'user',
    summary: "You have turned off 'get_object' for the 'task' service in Capabilities. Re-enable it there and retry.",
    surface: { kind: 'capabilities', section: 'services', entries: ['task'] },
  },
}

test('a user-fixable denial raises a card with the Capabilities affordance', () => {
  const state = chatReducer(initialState, chatActions.chatStep(stepEnvelope(USER_FIX_DENIAL)))
  assert.equal(state.banners.length, 1)
  const banner = state.banners[0]
  assert.equal(banner.text, USER_FIX_DENIAL.fix.summary)
  assert.deepEqual(banner.fixEntries, ['task'])
  assert.equal(banner.tone, 'warning')
  assert.equal(banner.placement, 'composer')
})

test('an admin-fixable denial states the fix with NO false affordance', () => {
  const denial = {
    ok: false,
    error: 'named_service_tool_not_allowed_for_client',
    message: "Client 'main' is not configured to call tool 'get_object' on namespace 'task'.",
    details: { namespace: 'task' },
    fix: {
      actor: 'admin',
      summary: "The app's configuration does not grant 'object.get' on the 'task' service to agent 'main'. An app admin can allow it under the agent's service configuration (namespaces.task.allowed).",
    },
  }
  const state = chatReducer(initialState, chatActions.chatStep(stepEnvelope(denial)))
  assert.equal(state.banners.length, 1)
  const banner = state.banners[0]
  assert.equal(banner.text, denial.fix.summary)
  assert.equal(banner.fixEntries, undefined)
  assert.equal(banner.actionUrl, undefined)
})

test('a provider-declared url fix renders the deep-link action', () => {
  const denial = {
    ok: false,
    error: 'task_issue_attachment_read_denied',
    message: 'Attachment belongs to an issue outside your access.',
    fix: {
      actor: 'provider',
      summary: 'This attachment belongs to a task issue outside your access. Review the issue on the Tasks board or ask its owner to share it.',
      surface: { kind: 'url', url: '/api/integrations/bundles/t/p/task-tracker@1-0/widgets/task_tracker_tasks', label: 'Open Tasks' },
    },
  }
  const state = chatReducer(initialState, chatActions.chatStep(stepEnvelope(denial)))
  const banner = state.banners[0]
  assert.equal(banner.actionUrl, denial.fix.surface.url)
  assert.equal(banner.actionLabel, 'Open Tasks')
  assert.equal(banner.fixEntries, undefined)
})

test('the fix payload is found nested inside a tool-result record', () => {
  const state = chatReducer(
    initialState,
    chatActions.chatStep(stepEnvelope({ result: { payload: USER_FIX_DENIAL } })),
  )
  assert.equal(state.banners.length, 1)
  assert.deepEqual(state.banners[0].fixEntries, ['task'])
})

test('the same denial is deduped; a dismissed signature stays quiet', () => {
  let state = chatReducer(initialState, chatActions.chatStep(stepEnvelope(USER_FIX_DENIAL)))
  state = chatReducer(state, chatActions.chatStep(stepEnvelope(USER_FIX_DENIAL, { turnId: 't2' })))
  assert.equal(state.banners.length, 1)
})

test('consent payloads keep their own card path (never matched as a fix)', () => {
  const consent = {
    ok: false,
    error: { code: 'needs_connected_account_consent', message: 'Connect Google / Gmail.' },
    fix: { actor: 'user', summary: 'should never render as a fix card' },
  }
  const state = chatReducer(initialState, chatActions.chatStep(stepEnvelope(consent)))
  const fixCard = state.banners.find((banner) => banner.text.includes('should never render'))
  assert.equal(fixCard, undefined)
})

test('an agent-actor fix raises NO banner (the model reroutes in-turn)', () => {
  // Intentional exclusion with a declared alternative: the fix instructs the
  // MODEL (react.pull path); there is nothing for the user to change.
  const denial = {
    ok: false,
    error: 'named_service_tool_not_allowed_for_client',
    message: "'object.get' on namespace 'task' rides another path for this agent; fix.summary names it.",
    details: { namespace: 'task', tool: 'get_object', client_id: 'main' },
    fix: {
      actor: 'agent',
      summary: 'Read a task object by pulling its ref with react.pull; read the materialized conv:fi: artifact with react.read.',
      reason: 'Reading rides the context tools — the agent pulls task refs directly.',
    },
  }
  const state = chatReducer(initialState, chatActions.chatStep(stepEnvelope(denial)))
  assert.equal(state.banners.length, 0)
})

test('an error without a declared fix raises no card (no invented affordances)', () => {
  const denial = { ok: false, error: 'task_ref_required', message: 'Task ref required.' }
  const state = chatReducer(initialState, chatActions.chatStep(stepEnvelope(denial)))
  assert.equal(state.banners.length, 0)
})
