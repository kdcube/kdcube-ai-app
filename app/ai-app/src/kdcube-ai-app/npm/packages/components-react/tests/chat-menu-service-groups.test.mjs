import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import {
  buildRealmGroups,
  classifyRealmEntry,
  namespaceGroupTogglePatch,
  namespaceState,
  openSurfaceOnHost,
  REALM_GROUP_LABELS,
} from '../../components-core/dist/chat/index.js'

// The service card reorganizes into grant-style Read / Create & update /
// Actions groups — toggleable as a UNIT, grammar tokens demoted to an
// expandable details. Excluded operations collapse to one quiet line. These
// pin the pure grouping + toggle logic and the card's source contract.

const CANVAS_REALM = {
  label: 'Canvas',
  operations: [
    { name: 'provider.about', label: 'Service overview' },
    { name: 'object.list', label: 'List boards' },
    { name: 'object.search', label: 'Search cards' },
    { name: 'object.schema', label: 'Object reference' },
    { name: 'object.upsert', label: 'Pin to a board' },
    // advertised but excluded for this agent
    { name: 'object.delete', label: 'Delete a card', enabled_for_agent: false },
    { name: 'object.get', label: 'Read one card', enabled_for_agent: false },
  ],
  actions: [],
}

test('operations classify into read / write / actions', () => {
  assert.equal(classifyRealmEntry('operation', 'object.list'), 'read')
  assert.equal(classifyRealmEntry('operation', 'provider.about'), 'read')
  assert.equal(classifyRealmEntry('operation', 'object.upsert'), 'write')
  assert.equal(classifyRealmEntry('operation', 'object.delete'), 'write')
  assert.equal(classifyRealmEntry('operation', 'object.host_file'), 'write')
  assert.equal(classifyRealmEntry('action', 'send'), 'actions')
  // undeclared mutating verb leans write, never silently "read"
  assert.equal(classifyRealmEntry('operation', 'object.publish'), 'write')
})

test('buildRealmGroups splits enabled entries into groups + collapses excluded', () => {
  const { groups, excluded } = buildRealmGroups(CANVAS_REALM)
  const byId = Object.fromEntries(groups.map((g) => [g.id, g]))
  assert.deepEqual(groups.map((g) => g.id), ['read', 'write'])
  assert.equal(byId.read.label, REALM_GROUP_LABELS.read)
  // human summary, no grammar tokens
  assert.equal(byId.read.summary, 'Service overview · List boards · Search cards · Object reference')
  assert.ok(!/object\./.test(byId.read.summary), 'no grammar tokens in the group summary')
  assert.equal(byId.write.summary, 'Pin to a board')
  // excluded entries leave the default groups; two collapse away
  assert.equal(excluded.length, 2)
  assert.deepEqual(excluded.map((e) => e.name).sort(), ['object.delete', 'object.get'])
  // group keys are the deny keys for those entries
  assert.deepEqual(byId.write.keys, ['object.upsert'])
})

test('a group toggle denies every group key as one unit and collapses forms', () => {
  const { groups } = buildRealmGroups(CANVAS_REALM)
  const entryKeys = groups.flatMap((g) => g.keys)
  const read = groups.find((g) => g.id === 'read')

  // turning READ off from a clean state denies exactly the read keys
  const off = namespaceGroupTogglePatch('cnv', entryKeys, read.keys, {})
  assert.deepEqual([...(off.named_services.cnv)].sort(), [...read.keys].sort())

  // group state reads off once its keys are denied, write stays on
  const disabled = { named_services: { cnv: read.keys } }
  assert.equal(namespaceState('cnv', read.keys, disabled), 'off')
  const write = groups.find((g) => g.id === 'write')
  assert.equal(namespaceState('cnv', write.keys, disabled), 'on')

  // denying the remaining group too collapses to the whole-namespace `true`
  const collapse = namespaceGroupTogglePatch('cnv', entryKeys, write.keys, disabled)
  assert.equal(collapse.named_services.cnv, true)

  // re-enabling a group from a whole-namespace deny leaves the rest denied
  const reopen = namespaceGroupTogglePatch('cnv', entryKeys, read.keys, { named_services: { cnv: true } })
  assert.deepEqual([...(reopen.named_services.cnv)].sort(), [...write.keys].sort())
})

test('openSurfaceOnHost resolves false in a standalone (no parent) context', async () => {
  // No embedding frame -> no ack -> caller keeps its URL fallback.
  assert.equal(await openSurfaceOnHost('task_tracker.issue_list', {}, { win: null }), false)
  assert.equal(await openSurfaceOnHost('', {}, { win: null }), false)
})

const SOURCE = readFileSync(
  new URL('../src/chat/ui/features/composer/ComposerMenu.tsx', import.meta.url),
  'utf8',
)

test('the service card renders grant-style groups, not a flat op list', () => {
  assert.match(SOURCE, /buildRealmGroups\(realm\)/)
  assert.match(SOURCE, /namespaceGroupTogglePatch\(namespace, entryKeys, group\.keys, disabled\)/)
  // details expander lives on the group, grammar rows come from RealmEntryRow
  assert.match(SOURCE, /function RealmGroupRow/)
  assert.match(SOURCE, /group\.entries\.map/)
})

test('the excluded wall collapses to one quiet expandable line', () => {
  assert.match(SOURCE, /function ExcludedSummary/)
  assert.match(SOURCE, /more operation/)
  assert.match(SOURCE, /<ExcludedSummary namespace=\{entry\.namespace\} excluded=\{excluded\} \/>/)
})

test('a declared exclusion renders its reason, not the admin sentence', () => {
  // buildRealmGroups passes declared notes through untouched on excluded rows
  const realm = {
    operations: [
      { name: 'object.list', label: 'List issues' },
      {
        name: 'object.get',
        label: 'Read an issue',
        enabled_for_agent: false,
        excluded_note: 'Reading rides the context tools — the agent pulls task refs directly.',
      },
      { name: 'object.delete', label: 'Delete an issue', enabled_for_agent: false },
    ],
    actions: [],
  }
  const { excluded } = buildRealmGroups(realm)
  const byName = Object.fromEntries(excluded.map((e) => [e.name, e]))
  assert.match(byName['object.get'].excluded_note, /rides the context tools/)
  assert.equal(byName['object.delete'].excluded_note, undefined)
  // the row: only the entry's own description/declared note — the admin fix
  // path lives ONCE, on the summary line's tooltip, never repeated per row
  assert.match(SOURCE, /const note = String\(entry\.excluded_note \|\| ''\)\.trim\(\)/)
  const excludedRow = SOURCE.slice(
    SOURCE.indexOf('function ExcludedEntryRow'),
    SOURCE.indexOf('\nfunction ', SOURCE.indexOf('function ExcludedEntryRow') + 10),
  )
  assert.doesNotMatch(excludedRow, /app admin/)
  assert.doesNotMatch(excludedRow, /namespaces\./)
  // the collapsed line speaks coverage when every exclusion declares its path
  assert.match(SOURCE, /allDeclared/)
  assert.match(SOURCE, /covered through other tools/)
})

test('the requirement affordance sits in-flow and prefers an on-scene summon', () => {
  // text + aside are siblings in flow (no chip crammed into the 16px state box)
  assert.match(SOURCE, /k-menu-requirement-text/)
  assert.match(SOURCE, /k-menu-requirement-aside/)
  // summon-first, URL new-tab fallback
  assert.match(SOURCE, /openSurfaceOnHost\(targetSurface/)
  assert.match(SOURCE, /if \(!acked\) openFallback\(\)/)
})

const STYLESHEETS = [
  new URL('../examples/standalone/chat-ui.css', import.meta.url),
  new URL(
    '../../../../kdcube_ai_app/apps/chat/sdk/solutions/chat/ui/widget/src/index.css',
    import.meta.url,
  ),
]

test('both stylesheet twins carry the group / excluded / requirement styles', () => {
  for (const href of STYLESHEETS) {
    const css = readFileSync(href, 'utf8')
    assert.match(css, /\.k-menu-group\b/, `${href} missing .k-menu-group`)
    assert.match(css, /\.k-menu-excluded-summary\b/, `${href} missing .k-menu-excluded-summary`)
    assert.match(css, /\.k-menu-requirement\b/, `${href} missing .k-menu-requirement`)
    assert.match(css, /\.k-menu-requirement-aside\b/, `${href} missing .k-menu-requirement-aside`)
  }
})
