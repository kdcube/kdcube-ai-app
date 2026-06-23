import {
  INGRESS_DRAG_END_MESSAGE_TYPE,
  INGRESS_DRAG_START_MESSAGE_TYPE,
  INGRESS_MESSAGE_TYPE,
} from '@kdcube/components-core/canvas'

export const CANVAS_INGRESS_MESSAGE_TYPE = INGRESS_MESSAGE_TYPE

const DURABLE_FI_REF = /^fi:conv_[^.]+\.turn_[^.]+\./
const NAMESPACE_REF = /^[a-z][a-z0-9_.-]*:/i
const BROWSER_SCHEMES = new Set(['blob:', 'data:', 'http:', 'https:', 'javascript:', 'mailto:'])

export function isDurableFiRef(ref: string): boolean {
  return DURABLE_FI_REF.test(ref)
}

export interface ChatFileDragInput {
  ref: string
  filename: string
  mime?: string | null
  preview?: string | null
  sourceKind: 'assistant.file' | 'user.attachment'
}

export function canonicalObjectRef(...refs: Array<string | null | undefined>): string {
  for (const raw of refs) {
    const ref = typeof raw === 'string' ? raw.trim() : ''
    if (!ref) continue
    if (ref.startsWith('fi:')) {
      if (isDurableFiRef(ref)) return ref
      continue
    }
    const scheme = (ref.match(NAMESPACE_REF)?.[0] || '').toLowerCase()
    if (scheme && !BROWSER_SCHEMES.has(scheme)) return ref
  }
  return ''
}

export function chatFileDragMessage(input: ChatFileDragInput) {
  return {
    type: CANVAS_INGRESS_MESSAGE_TYPE,
    payload: {
      object_ref: input.ref,
      mime: input.mime || 'application/octet-stream',
      title: input.filename,
      filename: input.filename,
      preview: input.preview || undefined,
      presentation: {
        label: input.sourceKind === 'user.attachment' ? 'attachment' : 'file',
      },
    },
  }
}

function postParentDragMessage(message: Record<string, unknown>): void {
  if (typeof window === 'undefined' || !window.parent || window.parent === window) return
  window.parent.postMessage(message, '*')
}

// Structural source for drag coordinates — accepts both a DOM DragEvent (the
// dragend listener) and a React.DragEvent (the start callers) without importing React.
interface DragPointSource { clientX: number; clientY: number; screenX: number; screenY: number }
function dragPoint(event: DragPointSource): Record<string, number> {
  return {
    client_x: event.clientX,
    client_y: event.clientY,
    screen_x: event.screenX,
    screen_y: event.screenY,
  }
}

export function setChatFileDragData(dataTransfer: DataTransfer, input: ChatFileDragInput, event?: DragPointSource): void {
  const message = chatFileDragMessage(input)
  dataTransfer.effectAllowed = 'copy'
  dataTransfer.setData('application/json', JSON.stringify(message))
  dataTransfer.setData('text/plain', input.filename)
  if (input.ref) {
    dataTransfer.setData('text/uri-list', input.ref)
  }
  postParentDragMessage({
    type: INGRESS_DRAG_START_MESSAGE_TYPE,
    source: 'chat-widget',
    ingress: message,
    // Include the dragstart point so the host can build a screen->client
    // calibration delta. Without it a cross-origin drop (released outside this
    // iframe, e.g. on the canvas) can't be mapped to host coordinates and misses
    // every drop target — context drags work only because they send this.
    ...(event ? dragPoint(event) : {}),
  })
  window.addEventListener('dragend', (endEvent) => {
    postParentDragMessage({ type: INGRESS_DRAG_END_MESSAGE_TYPE, source: 'chat-widget', ...dragPoint(endEvent) })
  }, { once: true })
}
