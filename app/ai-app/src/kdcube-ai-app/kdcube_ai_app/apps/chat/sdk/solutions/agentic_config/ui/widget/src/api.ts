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
  items: string[]
  status: string
  created_by: string
  created_at?: string | null
  updated_by?: string
  updated_at?: string | null
  versions?: InstructionVersionRow[]
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
  error?: OpError | string | null
  message?: string
}

function opsUrl(): string {
  const tenant = encodeURIComponent(settings.getTenant())
  const project = encodeURIComponent(settings.getProject())
  const bundle = encodeURIComponent(settings.getOpsBundle())
  return `${settings.getBaseUrl()}/api/integrations/bundles/${tenant}/${project}/${bundle}/operations/agentic_instructions`
}

async function call(data: Record<string, unknown>): Promise<OpEnvelope> {
  const response = await fetch(opsUrl(), {
    method: 'POST',
    credentials: 'include',
    headers: settings.authHeaders({ 'Content-Type': 'application/json', Accept: 'application/json' }),
    body: JSON.stringify({ data }),
  })
  const payload = (await response.json().catch(() => null)) as OpEnvelope | null
  if (!payload) throw new Error(`request failed (${response.status})`)
  return payload
}

export function errorText(envelope: OpEnvelope): string {
  const err = envelope.error
  if (err && typeof err === 'object') return err.message || err.code
  return String(err || envelope.message || 'request failed')
}

export async function listInstructions(includeRetired: boolean): Promise<InstructionRecord[]> {
  const envelope = await call({ action: 'list', include_retired: includeRetired })
  if (!envelope.ok) throw new Error(errorText(envelope))
  return envelope.ret?.items ?? []
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
