/** Parent-broker postMessage protocol for component-originated canvas ingress.
 *
 * Native drag-and-drop does not cross iframe boundaries reliably, so the
 * source iframe forwards drag intents as structured messages to the parent
 * main UI. The main UI normalizes the payload through
 * canvas ingress helpers and writes the resulting card via the configured
 * canvas mutation operation.
 *
 * The canonical wire shape is structural:
 *   - `payload.object_ref`: an existing canonical object URI/ref that flows
 *     through verbatim and resolves through the owner resolver.
 *   - `payload.content.text`: raw text content the receiving canvas
 *     materializes.
 *
 * The bridge is intentionally tiny and stateless so chat and canvas can
 * remain separate SDK-extractable components. The main UI is the only
 * place that decides which board the card lands on.
 */

export const INGRESS_MESSAGE_TYPE = 'kdcube.canvas.ingress'
export const INGRESS_DRAG_START_MESSAGE_TYPE = 'kdcube.canvas.ingress.drag_start'
export const INGRESS_DRAG_END_MESSAGE_TYPE = 'kdcube.canvas.ingress.drag_end'

export interface CanvasIngressPresentation {
  /** Cosmetic label only. It must not drive routing or object behavior. */
  label?: string
  /** Optional presentation lookup key supplied by the object owner/source. */
  object_kind?: string
  /** Optional root namespace label supplied by the object owner/source. */
  namespace?: string
}

export interface CanvasIngressSource {
  surface_ref?: string
  component?: string
  app?: string
  runtime?: string
  tenant?: string
  project?: string
  conversation_id?: string
  turn_id?: string
}

/** Existing object drop. The source component already knows the canonical
 *  resolver ref of the row; the main UI never parses it for behavior. */
export interface CanvasIngressObjectRefPayload {
  /** Canonical resolver ref. It flows through verbatim. */
  object_ref: string
  mime?: string
  title?: string
  namespace?: string
  object_kind?: string
  filename?: string
  presentation?: CanvasIngressPresentation
  /** Optional UI-only preview text for the card title before the ref
   *  resolves. */
  preview?: string
  /** Echo of the source component/turn so the main UI can attribute the card
   *  if it wants. Optional. */
  source?: CanvasIngressSource
}

/** Raw text drop. The text can come from chat, a document viewer, another
 *  widget, or future component sources. */
export interface CanvasIngressTextPayload {
  content: {
    mime?: string
    text: string
  }
  /** Optional preview/title hint; if absent the normalizer derives one
   *  from the leading characters of `text`. */
  title?: string
  presentation?: CanvasIngressPresentation
  source?: CanvasIngressSource
}

export type CanvasIngressPayload =
  | CanvasIngressObjectRefPayload
  | CanvasIngressTextPayload

export interface CanvasIngressMessage {
  type: typeof INGRESS_MESSAGE_TYPE
  payload: CanvasIngressPayload
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function trimOrUndefined(value: unknown): string | undefined {
  const str = asString(value).trim()
  return str || undefined
}

function parseSource(value: unknown): CanvasIngressSource | undefined {
  if (!value || typeof value !== 'object') return undefined
  const record = value as Record<string, unknown>
  const surface_ref = trimOrUndefined(record.surface_ref ?? record.surfaceRef)
  const component = trimOrUndefined(record.component)
  const app = trimOrUndefined(record.app)
  const runtime = trimOrUndefined(record.runtime)
  const tenant = trimOrUndefined(record.tenant)
  const project = trimOrUndefined(record.project)
  const conversation_id = trimOrUndefined(record.conversation_id ?? record.conversationId)
  const turn_id = trimOrUndefined(record.turn_id ?? record.turnId)
  if (!surface_ref && !component && !app && !runtime && !tenant && !project && !conversation_id && !turn_id) return undefined
  return { surface_ref, component, app, runtime, tenant, project, conversation_id, turn_id }
}

function parsePresentation(value: unknown): CanvasIngressPresentation | undefined {
  if (!value || typeof value !== 'object') return undefined
  const record = value as Record<string, unknown>
  const label = trimOrUndefined(record.label)
  const object_kind = trimOrUndefined(record.object_kind ?? record.objectKind)
  const namespace = trimOrUndefined(record.namespace)
  if (!label && !object_kind && !namespace) return undefined
  return { label, object_kind, namespace }
}

export function isCanvasIngressObjectRefPayload(payload: CanvasIngressPayload): payload is CanvasIngressObjectRefPayload {
  return typeof (payload as CanvasIngressObjectRefPayload).object_ref === 'string'
}

export function isCanvasIngressTextPayload(payload: CanvasIngressPayload): payload is CanvasIngressTextPayload {
  const content = (payload as CanvasIngressTextPayload).content
  return Boolean(content && typeof content === 'object' && typeof content.text === 'string')
}

/** Normalize an inbound postMessage envelope. Returns `null` when the data
 *  is not a recognized ingress message; defensive on every shape so a
 *  malformed payload never throws into the main UI's event loop. */
export function parseIngressMessage(data: unknown): CanvasIngressMessage | null {
  if (!data || typeof data !== 'object') return null
  const record = data as Record<string, unknown>
  if (record.type !== INGRESS_MESSAGE_TYPE) return null
  const payloadRaw = record.payload && typeof record.payload === 'object'
    ? record.payload as Record<string, unknown>
    : record
  const payload = payloadRaw
  const objectRef = asString(payload.object_ref ?? payload.objectRef).trim()
  if (objectRef) {
    const result: CanvasIngressObjectRefPayload = {
      object_ref: objectRef,
    }
    const mime = trimOrUndefined(payload.mime)
    if (mime) result.mime = mime
    const title = trimOrUndefined(payload.title)
    if (title) result.title = title
    const namespace = trimOrUndefined(payload.namespace)
    if (namespace) result.namespace = namespace
    const objectKind = trimOrUndefined(payload.object_kind ?? payload.objectKind)
    if (objectKind) result.object_kind = objectKind
    const filename = trimOrUndefined(payload.filename)
    if (filename) result.filename = filename
    const presentation = parsePresentation(payload.presentation)
    if (presentation) result.presentation = presentation
    const preview = trimOrUndefined(payload.preview)
    if (preview) result.preview = preview
    const source = parseSource(payload.source)
    if (source) result.source = source
    return { type: INGRESS_MESSAGE_TYPE, payload: result }
  }

  const contentRaw = payload.content
  const content = contentRaw && typeof contentRaw === 'object' ? contentRaw as Record<string, unknown> : null
  const text = asString(content?.text)
  if (text.trim()) {
    const result: CanvasIngressTextPayload = {
      content: {
        text,
      },
    }
    const mime = trimOrUndefined(content?.mime ?? payload.mime)
    if (mime) result.content.mime = mime
    const title = trimOrUndefined(payload.title)
    if (title) result.title = title
    const presentation = parsePresentation(payload.presentation)
    if (presentation) result.presentation = presentation
    const source = parseSource(payload.source)
    if (source) result.source = source
    return { type: INGRESS_MESSAGE_TYPE, payload: result }
  }

  return null
}

/** Build the envelope for chat side to post. Kept here so the message type
 *  string only has one home in the codebase. */
export function buildIngressMessage(payload: CanvasIngressPayload): CanvasIngressMessage {
  if (isCanvasIngressObjectRefPayload(payload) || isCanvasIngressTextPayload(payload)) {
    return { type: INGRESS_MESSAGE_TYPE, payload }
  }
  throw new Error('Unsupported canvas ingress payload shape')
}
