import { requestHostObjectOpen } from '../../host.ts'
import {
  downloadObjectActionResult,
  ObjectActionRequestError,
  resolveObjectAction,
  type BannerTone,
  type ObjectActionCapabilities,
  type ObjectActionName,
  type ObjectActionResponse,
} from '../../service.ts'
import type { AttachedContext } from './chatTypes.ts'
import type { ContextChip } from './contextChips.ts'

export type ActionableContext = AttachedContext | ContextChip

export class ContextPinActionError extends Error {
  readonly tone: BannerTone

  constructor(message: string, tone: BannerTone = 'warning') {
    super(message)
    this.name = 'ContextPinActionError'
    this.tone = tone
  }
}

export function contextPinActionNotice(error: unknown): { text: string; tone: BannerTone } {
  if (error instanceof ContextPinActionError) {
    return { text: error.message, tone: error.tone }
  }
  return {
    text: error instanceof Error ? error.message : String(error),
    tone: 'error',
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function field(record: Record<string, unknown>, ...keys: string[]): string {
  for (const key of keys) {
    const value = stringValue(record[key])
    if (value) return value
  }
  return ''
}

function looksLikeRef(value: string): boolean {
  return /^[a-z][a-z0-9+.-]*:/i.test(value) || value.startsWith('/')
}

export function contextPinObjectRef(context: ActionableContext): string {
  const record = asRecord(context)
  const data = asRecord(record.data)
  const direct = field(record, 'ref', 'logicalPath', 'logical_path', 'hostedUri', 'hosted_uri', 'object_ref', 'event_ref', 'uri', 'canonical_uri')
  if (direct) return direct
  const nested = field(data, 'ref', 'logicalPath', 'logical_path', 'hostedUri', 'hosted_uri', 'object_ref', 'event_ref', 'uri', 'canonical_uri')
  if (nested) return nested
  const id = field(record, 'id')
  return looksLikeRef(id) ? id : ''
}

function contextLabel(context: ActionableContext, objectRef: string): string {
  const record = asRecord(context)
  return field(record, 'label', 'title', 'id') || objectRef || 'context'
}

function contextMime(context: ActionableContext): string {
  const record = asRecord(context)
  const data = asRecord(record.data)
  return field(record, 'mime', 'media_type', 'content_type') || field(data, 'mime', 'media_type', 'content_type')
}

function isAction(value: string): value is ObjectActionName {
  return ['capabilities', 'describe', 'preview', 'open', 'download', 'rehost'].includes(value)
}

function capabilitiesFrom(response: ObjectActionResponse): ObjectActionCapabilities {
  return response.capabilities && typeof response.capabilities === 'object' ? response.capabilities : {}
}

function openEffectActionFrom(response: ObjectActionResponse): ObjectActionName | '' {
  const record = response as Record<string, unknown>
  const extra = asRecord(record.extra)
  const value =
    field(record, 'default_open_effect_action', 'defaultOpenEffectAction') ||
    field(extra, 'default_open_effect_action', 'defaultOpenEffectAction')
  return isAction(value) ? value : ''
}

export function chooseContextPinOpenEffectAction(
  capabilitiesResponse: ObjectActionResponse,
): ObjectActionName | '' {
  const capabilities = capabilitiesFrom(capabilitiesResponse)
  const declaredOpenEffect = openEffectActionFrom(capabilitiesResponse)
  if ((declaredOpenEffect === 'open' || declaredOpenEffect === 'download') && capabilities[declaredOpenEffect] !== false) {
    return declaredOpenEffect
  }
  return ''
}

function sourceForContext(context: ActionableContext, objectRef: string): Record<string, unknown> {
  const record = asRecord(context)
  return {
    id: field(record, 'id') || objectRef,
    title: contextLabel(context, objectRef),
    summary: field(record, 'summary'),
    kind: field(record, 'kind', 'cardType', 'card_type') || 'context',
    ref: objectRef,
    mime: contextMime(context) || 'application/octet-stream',
  }
}

function isResolverUnavailable(error: unknown): boolean {
  if (!(error instanceof ObjectActionRequestError)) return false
  const code = String(error.code || '').toLowerCase()
  return error.action === 'capabilities' && (
    code.includes('resolver_not_registered') ||
    code.includes('not_registered') ||
    error.status === 404
  )
}

export async function activateContextPin(context: ActionableContext): Promise<void> {
  const objectRef = contextPinObjectRef(context)
  if (!objectRef) {
    throw new ContextPinActionError(`No open/download action is registered for "${contextLabel(context, '')}".`)
  }
  const filename = contextLabel(context, objectRef)
  const mime = contextMime(context) || undefined
  let capabilities: ObjectActionResponse
  try {
    capabilities = await resolveObjectAction({
      action: 'capabilities',
      objectRef,
      filename,
      mime,
    })
  } catch (error) {
    if (isResolverUnavailable(error)) {
      throw new ContextPinActionError(`No open/download action is registered for "${filename}".`)
    }
    throw error
  }
  const action = chooseContextPinOpenEffectAction(capabilities)
  if (!action) {
    throw new ContextPinActionError(`No open/download action is available for "${filename}".`)
  }
  const response = await resolveObjectAction({
    action,
    objectRef,
    filename,
    mime,
  })
  if (action === 'download') {
    downloadObjectActionResult(response, filename, mime)
    return
  }
  if (action === 'open') {
    const posted = requestHostObjectOpen({
      response: response as Record<string, unknown>,
      source: sourceForContext(context, objectRef),
    })
    if (!posted) {
      throw new ContextPinActionError(`No host surface is available to open "${filename}".`, 'error')
    }
  }
}
