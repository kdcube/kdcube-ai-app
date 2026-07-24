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
