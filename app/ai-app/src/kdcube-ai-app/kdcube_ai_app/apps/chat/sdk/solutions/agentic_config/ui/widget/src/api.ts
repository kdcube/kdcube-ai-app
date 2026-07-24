/**
 * Client for the `agentic_instructions` operation on `kdcube-services@1-0`
 * (the bundle that owns the `instr` namespace). One POST route; the action
 * rides the body. Writes are admin-gated SERVER-SIDE — this client sends the
 * caller's identity and renders the structured denial when it is not enough.
 */

import { settings } from './settings.ts'

export interface InstructionVersionRow {
  version: number
  status: string
  created_by: string
  created_at?: string | null
}

export interface InstructionRecord {
  ref: string
  instruction_id: string
  version: number
  name: string
  description: string
  tags: string[]
  items: string[]
  status: string
  created_by: string
  created_at?: string | null
  updated_by?: string
  updated_at?: string | null
  versions?: InstructionVersionRow[]
}

export interface BuiltinBlock {
  name: string
  tier: string
  description: string
  tags: string[]
}

export interface OpError {
  code: string
  message: string
}

interface OpEnvelope {
  ok: boolean
  ret?: {
    object?: InstructionRecord
    items?: InstructionRecord[]
    attrs?: Record<string, unknown>
  }
  body?: string
  items_expanded?: string[]
  blocks?: BuiltinBlock[]
  error?: OpError | string | null
  message?: string
  /** FastAPI-level rejection (auth/route), not the op envelope. */
  detail?: string
  /** transport status, attached client-side for legible errors */
  http_status?: number
}

function opsUrl(): string {
  const tenant = encodeURIComponent(settings.getTenant())
  const project = encodeURIComponent(settings.getProject())
  const bundle = encodeURIComponent(settings.getOpsBundle())
  return `${settings.getBaseUrl()}/api/integrations/bundles/${tenant}/${project}/${bundle}/operations/agentic_instructions`
}

async function call(data: Record<string, unknown>): Promise<OpEnvelope> {
  const url = opsUrl()
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: settings.authHeaders({ 'Content-Type': 'application/json', Accept: 'application/json' }),
    body: JSON.stringify({ data }),
  })
  const raw = (await response.json().catch(() => null)) as Record<string, unknown> | null
  if (!raw) throw new Error(`request failed (HTTP ${response.status} at ${url})`)
  // The operations route wraps the op's own result under its ALIAS key:
  // {status: "ok", tenant, project, bundle_id, agentic_instructions: {ok, ...}}.
  const inner = raw['agentic_instructions']
  const envelope = (
    inner && typeof inner === 'object' ? inner : raw
  ) as OpEnvelope
  envelope.http_status = response.status
  return envelope
}

export function errorText(envelope: OpEnvelope): string {
  const err = envelope.error
  const status = envelope.http_status ? ` (HTTP ${envelope.http_status})` : ''
  if (err && typeof err === 'object') return (err.message || err.code) + status
  const text = String(err || envelope.message || envelope.detail || 'request failed')
  return text + status
}

export async function listInstructions(
  includeRetired: boolean,
  q = '',
  tags: string[] = [],
): Promise<InstructionRecord[]> {
  const envelope = await call({ action: 'list', include_retired: includeRetired, q, tags })
  if (!envelope.ok) throw new Error(errorText(envelope))
  return envelope.ret?.items ?? []
}

/** The built-in block catalog (name, tier, description, tags) — what the
 *  constructor offers alongside stored units. */
export async function listBuiltinBlocks(): Promise<BuiltinBlock[]> {
  const envelope = await call({ action: 'blocks' })
  if (!envelope.ok) throw new Error(errorText(envelope))
  return envelope.blocks ?? []
}

export async function getInstruction(ref: string): Promise<InstructionRecord> {
  const envelope = await call({ action: 'get', ref })
  if (!envelope.ok) throw new Error(errorText(envelope))
  const record = envelope.ret?.object
  if (!record) throw new Error('instruction payload missing')
  return record
}

export async function saveVersion(input: {
  instruction_id: string
  name: string
  description: string
  tags: string[]
  items: string[]
}): Promise<InstructionRecord> {
  const envelope = await call({ action: 'save', ...input })
  if (!envelope.ok) throw new Error(errorText(envelope))
  const record = envelope.ret?.object
  if (!record) throw new Error('instruction payload missing')
  return record
}

export async function retireInstruction(ref: string): Promise<void> {
  const envelope = await call({ action: 'retire', ref })
  if (!envelope.ok) throw new Error(errorText(envelope))
}

export async function previewBody(items: string[], workspaceImplementation = 'custom'): Promise<{
  body: string
  items_expanded: string[]
}> {
  const envelope = await call({
    action: 'preview',
    items,
    workspace_implementation: workspaceImplementation,
  })
  if (!envelope.ok) throw new Error(errorText(envelope))
  return { body: envelope.body ?? '', items_expanded: envelope.items_expanded ?? [] }
}

// ── assignment: wire a stored instruction to an application agent ────────────
// Uses the platform admin routes (list bundles, read props, merge-write props).
// Assignment adds/updates an instruction-profile OPTION on the target agent
// whose id is the instruction slug and whose blocks wire the pinned ref —
// user-pickable immediately; optionally also made the profile default.

export interface AppEntry {
  bundleId: string
  name: string
}

function adminBase(): string {
  return `${settings.getBaseUrl()}/admin/integrations/bundles`
}

function scopeQuery(): string {
  return `tenant=${encodeURIComponent(settings.getTenant())}&project=${encodeURIComponent(settings.getProject())}`
}

async function adminGet(url: string): Promise<Record<string, unknown>> {
  const response = await fetch(url, {
    method: 'GET',
    credentials: 'include',
    headers: settings.authHeaders({ Accept: 'application/json' }),
    cache: 'no-store',
  })
  const payload = (await response.json().catch(() => null)) as Record<string, unknown> | null
  if (!response.ok || !payload) {
    throw new Error(`${(payload as { detail?: string } | null)?.detail || 'request failed'} (HTTP ${response.status})`)
  }
  return payload
}

export async function listApps(): Promise<AppEntry[]> {
  const payload = await adminGet(`${adminBase()}?${scopeQuery()}`)
  const entries = (payload.available_bundles ?? {}) as Record<string, { name?: string }>
  return Object.keys(entries)
    .sort()
    .map((bundleId) => ({ bundleId, name: entries[bundleId]?.name || bundleId }))
}

function deepMerge(base: unknown, over: unknown): unknown {
  if (over === undefined || over === null) return base
  if (typeof base !== 'object' || base === null || Array.isArray(base)) return over
  if (typeof over !== 'object' || Array.isArray(over)) return over
  const out: Record<string, unknown> = { ...(base as Record<string, unknown>) }
  for (const key of Object.keys(over as Record<string, unknown>)) {
    out[key] = deepMerge((base as Record<string, unknown>)[key], (over as Record<string, unknown>)[key])
  }
  return out
}

/** The app's EFFECTIVE config (code defaults ← stored props) + its react agent keys. */
export async function getAppAgents(bundleId: string): Promise<{ agents: string[]; config: Record<string, unknown> }> {
  const payload = await adminGet(`${adminBase()}/${encodeURIComponent(bundleId)}/props?${scopeQuery()}`)
  const config = deepMerge(payload.defaults ?? {}, payload.props ?? {}) as Record<string, unknown>
  const react = config.react
  const agents = (react && typeof react === 'object' && !Array.isArray(react))
    ? Object.keys(react as Record<string, unknown>).filter((key) => {
        const value = (react as Record<string, unknown>)[key]
        return value && typeof value === 'object' && !Array.isArray(value)
      })
    : []
  return { agents: agents.length ? agents : ['default_agent'], config }
}

interface ProfileOption {
  id: string
  label?: string
  description?: string
  blocks?: string[]
  [key: string]: unknown
}

/** Add/update the instruction-profile option wiring `record` on the target
 *  agent, and merge-write the WHOLE instruction_profiles subtree (the admin
 *  merge replaces arrays, so the full options list rides the patch). */
export async function assignInstruction(
  bundleId: string,
  agentKey: string,
  record: InstructionRecord,
  options: { makeDefault?: boolean } = {},
): Promise<{ optionId: string }> {
  const { config } = await getAppAgents(bundleId)
  const react = (config.react ?? {}) as Record<string, unknown>
  const agentBlock = (react[agentKey] ?? {}) as Record<string, unknown>
  const profiles = (agentBlock.instruction_profiles ?? {}) as Record<string, unknown>
  const existing: ProfileOption[] = Array.isArray(profiles.options)
    ? (profiles.options as ProfileOption[]).map((row) => ({ ...row }))
    : []
  const ref = `instr:custom:${record.instruction_id}:${record.version}`
  const option: ProfileOption = {
    id: record.instruction_id,
    label: record.name || record.instruction_id,
    ...(record.description ? { description: record.description } : {}),
    blocks: [ref],
  }
  const index = existing.findIndex((row) => row.id === record.instruction_id)
  if (index >= 0) existing[index] = { ...existing[index], ...option }
  else existing.push(option)
  const nextProfiles: Record<string, unknown> = {
    ...profiles,
    options: existing,
    default: options.makeDefault
      ? record.instruction_id
      : (profiles.default ?? existing[0]?.id ?? record.instruction_id),
  }
  const response = await fetch(`${adminBase()}/${encodeURIComponent(bundleId)}/props`, {
    method: 'POST',
    credentials: 'include',
    headers: settings.authHeaders({ 'Content-Type': 'application/json', Accept: 'application/json' }),
    body: JSON.stringify({
      tenant: settings.getTenant(),
      project: settings.getProject(),
      op: 'merge',
      props: { react: { [agentKey]: { instruction_profiles: nextProfiles } } },
    }),
  })
  const payload = (await response.json().catch(() => null)) as Record<string, unknown> | null
  if (!response.ok || !payload || payload.status !== 'ok') {
    throw new Error(`${(payload as { detail?: string } | null)?.detail || 'assign failed'} (HTTP ${response.status})`)
  }
  return { optionId: record.instruction_id }
}
