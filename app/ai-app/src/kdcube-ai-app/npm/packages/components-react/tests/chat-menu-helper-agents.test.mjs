import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import {
  applySelectionPatch,
  isSubagentsDisabled,
  subagentsTogglePatch,
} from '../../components-core/dist/chat/index.js'

// The helper-agents row (ReAct subagents v2, the user's decision) and the
// subagent thread block. The row rides the shared picker body — one body,
// three shells (composer popover, expanded modal, served capabilities
// widget) — so pinning the section registration covers all three.

const MENU_SOURCE = readFileSync(
  new URL('../src/chat/ui/features/composer/ComposerMenu.tsx', import.meta.url),
  'utf8',
)

test('the helper-agents row rides the shared picker body via the sections registry', () => {
  assert.match(MENU_SOURCE, /function HelperAgentsSection/)
  assert.match(MENU_SOURCE, /capabilitySection\('subagents', 45, HelperAgentsSection\)/)
})

test('entry absent -> no row; copy comes from the payload, never hardcoded prose', () => {
  const section = MENU_SOURCE.slice(
    MENU_SOURCE.indexOf('function HelperAgentsSection'),
    MENU_SOURCE.indexOf('\nfunction ', MENU_SOURCE.indexOf('function HelperAgentsSection') + 10),
  )
  // gate: the inventory entry must be present AND available
  assert.match(section, /inventory\.subagents/)
  assert.match(section, /if \(!entry\?\.available\) return null/)
  // label + description render from the payload
  assert.match(section, /entry\.label/)
  assert.match(section, /sub=\{entry\.description/)
  // the description (trade-off copy) is server-owned: no cost/quality prose here
  assert.doesNotMatch(section, /billed|model calls|quality/i)
  // the toggle goes through the shared selection flow, seeded with the payload's
  // default_on so the unset state honors an admin default-off ability
  assert.match(section, /entry\.default_on !== false/)
  assert.match(section, /toggle\(subagentsTogglePatch\(disabled, defaultOn\)\)/)
  assert.match(section, /isSubagentsDisabled\(disabled, defaultOn\)/)
  // a deferred change badges the row like every other category
  assert.match(section, /pending\?\.disabled\?\.subagents/)
})

test('the toggle writes the explicit sub-agents preference both ways (opt-out / opt-in)', () => {
  assert.deepEqual(subagentsTogglePatch({}), { subagents: true })
  const off = applySelectionPatch({}, subagentsTogglePatch({}))
  assert.equal(isSubagentsDisabled(off), true)
  // turning it back ON writes and STORES the explicit opt-in `false`
  assert.deepEqual(subagentsTogglePatch(off), { subagents: false })
  assert.deepEqual(applySelectionPatch(off, subagentsTogglePatch(off)), { subagents: false })
})

test('the toggle honors the payload default_on when the user has no stored preference', () => {
  // unset + default-off renders off; the toggle then writes the opt-in `false`
  assert.equal(isSubagentsDisabled({}, false), true)
  assert.deepEqual(subagentsTogglePatch({}, false), { subagents: false })
  // unset + default-on renders on; the toggle writes the opt-out `true`
  assert.equal(isSubagentsDisabled({}, true), false)
  assert.deepEqual(subagentsTogglePatch({}, true), { subagents: true })
})

const THREADS_SOURCE = readFileSync(
  new URL('../src/chat/ui/features/chat/SubagentThreads.tsx', import.meta.url),
  'utf8',
)
const SHELL_SOURCE = readFileSync(
  new URL('../src/chat/ui/ChatShell.tsx', import.meta.url),
  'utf8',
)

test('threads anchor inline under their fork turn with the same rendering pipeline', () => {
  // anchored per turn in the message flow (no reserved columns/widths)
  assert.match(SHELL_SOURCE, /subagentThreadsForTurn\(state\.threads, turn\.id\)/)
  assert.match(SHELL_SOURCE, /<SubagentThreads/)
  // child turns render through the SAME ChatTurnView pipeline, nested
  assert.match(THREADS_SOURCE, /<ChatTurnView/)
  // collapsed header: charter goal + status + contribution milestones
  assert.match(THREADS_SOURCE, /charterGoal/)
  assert.match(THREADS_SOURCE, /ThreadStatusChip/)
  assert.match(THREADS_SOURCE, /contributions/)
  // expanding a reload stub fetches the child conversation
  assert.match(THREADS_SOURCE, /loadThread\(thread\.childConversationId\)/)
  assert.match(SHELL_SOURCE, /engine\.loadSubagentThread/)
})

test('the thread header shows the fixed SUB-AGENT kicker plus the chosen persona', () => {
  // fixed label word is SUB-AGENT
  assert.match(THREADS_SOURCE, /k-subthread-kicker">SUB-AGENT</)
  // the persona name still comes from the stamp/reload agent_title, fallback Sub-agent
  assert.match(THREADS_SOURCE, /thread\.agentTitle \|\| 'Sub-agent'/)
  assert.match(THREADS_SOURCE, /thread\.agentTitle \? `\$\{personaName\} · \$\{goal\}` : goal/)
  // no "helper" wording survives anywhere in the thread UI
  assert.doesNotMatch(THREADS_SOURCE, /[Hh]elper/)
})

const TURNVIEW_SOURCE = readFileSync(
  new URL('../src/chat/ui/features/chat/TurnView.tsx', import.meta.url),
  'utf8',
)

test('an agent-authored continuation turn renders as the sub-agent persona, not "You" (fix B)', () => {
  // the turn's triggering-input persona is read from the state model
  assert.match(TURNVIEW_SOURCE, /turn\.authoredBy/)
  // the persona name replaces "You"; the handoff renders as "<name> said: …"
  assert.match(TURNVIEW_SOURCE, /agentTitle \|\| 'Sub-agent'/)
  assert.match(TURNVIEW_SOURCE, /\{personaName\} said:/)
  // no contribution -> persona with a neutral line, never the raw event or "You"
  assert.match(TURNVIEW_SOURCE, /agentPersona\.handoff \?/)
})

const STYLESHEETS = [
  new URL('../examples/standalone/chat-ui.css', import.meta.url),
  new URL(
    '../../../../kdcube_ai_app/apps/chat/sdk/solutions/chat/ui/widget/src/index.css',
    import.meta.url,
  ),
]

test('both stylesheet twins carry the subagent thread styles', () => {
  for (const href of STYLESHEETS) {
    const css = readFileSync(href, 'utf8')
    assert.match(css, /\.k-subthread\b/, `${href} missing .k-subthread`)
    assert.match(css, /\.k-subthread-milestone\b/, `${href} missing .k-subthread-milestone`)
    assert.match(css, /\.k-subthread-body\b/, `${href} missing .k-subthread-body`)
  }
})
