import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  applySelectionPatch,
  isNamespaceDisabled,
  isNamespaceEntryDisabled,
  namespaceEntryKey,
  namespaceEntryTogglePatch,
  namespaceState,
  namespaceTogglePatch,
} from '../../components-core/dist/chat/index.js'

// The menu's namespace-narrowing flow at the rig's layer: entry keys, toggle
// patches, optimistic application — the same selection round-trip the server
// merge-write persists.

const KEYS = ['object.list', 'object.search', 'object.get', 'object.action.send', 'object.action.forward']

test('entry keys: operations by token, actions ride object.action', () => {
  assert.equal(namespaceEntryKey('operation', 'object.search'), 'object.search')
  assert.equal(namespaceEntryKey('action', 'send'), 'object.action.send')
})

test('toggling one entry denies exactly that entry, optimistically applied', () => {
  let disabled = {}
  const patch = namespaceEntryTogglePatch('mail', KEYS, disabled, 'object.action.send')
  assert.deepEqual(patch, { named_services: { mail: ['object.action.send'] } })
  disabled = applySelectionPatch(disabled, patch)
  assert.equal(isNamespaceEntryDisabled(disabled, 'mail', 'object.action.send'), true)
  assert.equal(isNamespaceEntryDisabled(disabled, 'mail', 'object.search'), false)
  assert.equal(isNamespaceDisabled(disabled, 'mail'), false)
  assert.equal(namespaceState('mail', KEYS, disabled), 'partial')
})

test('denying every entry collapses to the whole-namespace form', () => {
  let disabled = { named_services: { mail: KEYS.slice(0, -1) } }
  const patch = namespaceEntryTogglePatch('mail', KEYS, disabled, KEYS[KEYS.length - 1])
  assert.deepEqual(patch, { named_services: { mail: true } })
  disabled = applySelectionPatch(disabled, patch)
  assert.equal(namespaceState('mail', KEYS, disabled), 'off')
})

test('re-enabling the last denied entry clears the record', () => {
  let disabled = { named_services: { mail: ['object.search'] } }
  const patch = namespaceEntryTogglePatch('mail', KEYS, disabled, 'object.search')
  assert.deepEqual(patch, { named_services: { mail: false } })
  disabled = applySelectionPatch(disabled, patch)
  assert.equal(namespaceState('mail', KEYS, disabled), 'on')
})

test('turning one entry back on from a whole-realm deny keeps the rest off', () => {
  const disabled = { named_services: { mail: true } }
  const patch = namespaceEntryTogglePatch('mail', KEYS, disabled, 'object.list')
  assert.deepEqual(patch, {
    named_services: { mail: KEYS.filter((key) => key !== 'object.list') },
  })
})

test('namespace master toggle: on -> whole deny; partial/off -> re-enable all', () => {
  assert.deepEqual(namespaceTogglePatch('mail', KEYS, {}), { named_services: { mail: true } })
  assert.deepEqual(
    namespaceTogglePatch('mail', KEYS, { named_services: { mail: ['object.search'] } }),
    { named_services: { mail: false } },
  )
  assert.deepEqual(
    namespaceTogglePatch('mail', KEYS, { named_services: { mail: true } }),
    { named_services: { mail: false } },
  )
})
