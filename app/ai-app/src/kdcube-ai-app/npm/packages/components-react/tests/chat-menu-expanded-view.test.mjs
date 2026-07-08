import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { preferredMenuPresentation } from '../../components-core/dist/chat/index.js'

// The capability picker is ONE component with two presentations: the compact
// popover (quick toggles) and the wide canvas-modal shell where service-card
// prose wraps. These pin the presentation-switch contract at the rig's layer.

const STYLESHEETS = [
  new URL('../examples/standalone/chat-ui.css', import.meta.url),
  new URL(
    '../../../../kdcube_ai_app/apps/chat/sdk/solutions/chat/ui/widget/src/index.css',
    import.meta.url,
  ),
]

const INVENTORY = {
  named_services: [
    { namespace: 'mail', alias: 'named_services' },
    { namespace: 'slack', alias: 'named_services' },
  ],
}

test('spotlight on a namespace entry prefers the expanded view', () => {
  assert.equal(preferredMenuPresentation(['slack'], INVENTORY), 'modal')
  assert.equal(preferredMenuPresentation(['named_services'], INVENTORY), 'modal')
})

test('a short dedicated-tool spotlight stays in the popover', () => {
  assert.equal(preferredMenuPresentation(['slack_tools.search_slack'], INVENTORY), 'popover')
  assert.equal(preferredMenuPresentation([], INVENTORY), 'popover')
  assert.equal(preferredMenuPresentation(undefined, INVENTORY), 'popover')
})

test('a long target list prefers the expanded view', () => {
  assert.equal(preferredMenuPresentation(['a.b', 'a.c', 'a.d', 'a.e'], INVENTORY), 'modal')
})

const SOURCE = readFileSync(
  new URL('../src/chat/ui/features/composer/ComposerMenu.tsx', import.meta.url),
  'utf8',
)

test('one body renders into both shells (shared interaction state)', () => {
  // The body node is computed once, above the shells...
  const bodyRenders = SOURCE.match(/\{body\}/g) ?? []
  assert.equal(bodyRenders.length, 2, 'the same {body} mounts in the popover and in the modal')
  // ...and the confirm picker re-anchors when the presentation switches.
  assert.match(SOURCE, /\[confirmState, view\]/)
})

test('expand and collapse affordances are present', () => {
  assert.match(SOURCE, /CanvasExpandButton onClick=\{\(\) => setView\('modal'\)\}/)
  assert.match(SOURCE, /aria-label="Collapse to menu"/)
  assert.match(SOURCE, /aria-label="Close \(Esc\)"/)
})

for (const sheet of STYLESHEETS) {
  const label = sheet.pathname.split('/').slice(-3).join('/')
  const css = readFileSync(sheet, 'utf8')

  test(`expanded view wraps prose instead of ellipsizing (${label})`, () => {
    const start = css.indexOf('.k-menu-expanded .k-menu-row-sub')
    assert.ok(start >= 0, 'expanded wrap block exists')
    const block = css.slice(start, css.indexOf('}', start))
    assert.match(block, /white-space:\s*normal/)
    assert.match(block, /overflow:\s*visible/)
    assert.match(block, /text-overflow:\s*clip/)
  })

  test(`popover head carries the expand affordance styling (${label})`, () => {
    assert.ok(css.includes('.k-menu-head {'), '.k-menu-head exists')
    assert.ok(css.includes('.k-menu-head-label'), '.k-menu-head-label exists')
  })

  test(`modal body is a readable scrolling column (${label})`, () => {
    const start = css.indexOf('.k-menu-modal-body')
    assert.ok(start >= 0)
    const block = css.slice(start, css.indexOf('}', start))
    assert.match(block, /overflow:\s*auto/)
  })
}
