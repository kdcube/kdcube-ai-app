import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

// Regression: a minimal agent (a model list + a connections entry, no skills /
// namespaces / tools) must NOT render blank divider rows for the empty groups.
// The picker body filters out any section whose render returns null, then draws
// a divider only between the survivors — so an empty group must resolve to null
// at the descriptor level (a `<Section/>` element reads as truthy and can't be
// filtered). These pin that contract at the source layer (the suite has no DOM
// rig; the sections use hooks and can't be called as plain functions).

const MENU_SOURCE = readFileSync(
  new URL('../src/chat/ui/features/composer/ComposerMenu.tsx', import.meta.url),
  'utf8',
)

test('the picker body filters null section nodes, then divides only survivors', () => {
  // null-rendering sections are dropped BEFORE the divider/wrapper are drawn
  assert.match(MENU_SOURCE, /\.filter\(\(section\) => section\.node !== null/)
  // the divider rides `index > 0` over the FILTERED list, so no empty group
  // can leave a stray divider behind
  assert.match(MENU_SOURCE, /index > 0 \? <div className="k-menu-divider"/)
})

test('every capability section is gated by a hasItems predicate', () => {
  // the wrapper returns null when the group is empty
  assert.match(MENU_SOURCE, /if \(!inventory \|\| !hasItems\(inventory\)\) return null/)
  // each built-in capability group carries its own emptiness predicate
  assert.match(MENU_SOURCE, /capabilitySection\('skills', 10, \(inv\) => inv\.skills\.length > 0, SkillsSection\)/)
  assert.match(MENU_SOURCE, /capabilitySection\('tools', 20, \(inv\) => inv\.tools\.some\(\(group\) => !group\.system\), ToolGroupsSection\)/)
  assert.match(MENU_SOURCE, /capabilitySection\('mcp', 30, \(inv\) => inv\.mcp\.length > 0, McpSection\)/)
  assert.match(MENU_SOURCE, /capabilitySection\('services', 40, \(inv\) => inv\.named_services\.length > 0, ServicesSection\)/)
  assert.match(MENU_SOURCE, /capabilitySection\('subagents', 45, \(inv\) => Boolean\(inv\.subagents\?\.available\), HelperAgentsSection\)/)
})

test('the model and connections descriptors also resolve to null when empty', () => {
  // model: no admin-allowed list -> no section (never a blank row)
  assert.match(MENU_SOURCE, /supported_models\?\.length\s*\?\s*<ModelsSection/)
  // connections: no host handler -> no section
  assert.match(MENU_SOURCE, /connections\.available\(\) \? <ConnectorsSection \{\.\.\.ctx\} \/> : null/)
})
