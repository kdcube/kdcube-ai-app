/**
 * Conversation-open command recognition for the chat widget host bridge.
 *
 * A scene host asks the chat to switch conversations with a
 * `kdcube.surface.command` on the `sdk.chat.viewer` / `sdk.chat.conversation`
 * surfaces. The conversation identity arrives in one of three places,
 * depending on the emitter:
 *
 *   - `conversation_id` at the top level (provider-open dispatch spreads the
 *     resolver's ui_event into the command),
 *   - `ui_event.conversation_id` (the pin board forwards the resolver's
 *     ui_event verbatim; the website host carries it under `ui_event` too),
 *   - a canonical `conv:` object ref (`object_ref` / `context.ref`) — either
 *     the short `conv:<conversation_id>` form or the full positional
 *     `conv:<tenant>/<project>/<user>/<bundle>/<agent>/<conversation_id>`
 *     ref that pinned conversations carry (the conversation id is always the
 *     LAST segment).
 *
 * `conv:fi:` refs are conversation FILES, never a conversation to open.
 */

const SURFACE_COMMAND_MESSAGE_TYPE = 'kdcube.surface.command'
const CHAT_CONVERSATION_SURFACES = new Set(['sdk.chat.conversation', 'sdk.chat.viewer'])
const CONVERSATION_OPEN_ACTIONS = new Set(['open', 'attach', 'focus'])
const CONVERSATION_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]*$/

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

/** True for the conversation object kinds pins and contexts carry. */
export function isConversationKind(value: unknown): boolean {
  const text = String(value || '').trim().toLowerCase()
  return text === 'conversation' || text === 'chat.conversation'
}

/**
 * Conversation id from a canonical `conv:` ref — short (`conv:<id>`) or full
 * positional (`conv:.../<id>`, id last). '' for anything else, including
 * `conv:fi:` file refs.
 */
export function conversationIdFromConversationRef(ref: string): string {
  const value = String(ref || '').trim()
  if (!value.startsWith('conv:')) return ''
  const body = value.slice('conv:'.length).trim()
  if (!body || body.startsWith('fi:')) return ''
  const segments = body.split('/')
  const id = (segments[segments.length - 1] || '').trim()
  if (!id || !CONVERSATION_ID_PATTERN.test(id)) return ''
  return id
}

/**
 * Conversation id carried by one context item (a dragged pin, an attach
 * payload entry): explicit `conversation_id` first, then the item's `conv:`
 * ref when its kind marks it a conversation or the ref itself parses.
 */
export function conversationIdFromContextItem(item: unknown): string {
  const record = recordValue(item)
  if (!Object.keys(record).length) return ''
  const data = recordValue(record.data)
  const kind = record.kind ?? record.object_kind ?? record.objectKind ?? data.object_kind ?? data.objectKind
  const ref = stringValue(record.ref) ||
    stringValue(record.object_ref) ||
    stringValue(record.logical_path) ||
    stringValue(record.id) ||
    stringValue(data.object_ref) ||
    stringValue(data.ref) ||
    stringValue(data.logical_path)
  const fromRef = conversationIdFromConversationRef(ref)
  if (!isConversationKind(kind) && !fromRef) return ''
  const direct = stringValue(data.conversation_id) || stringValue(record.conversation_id)
  return direct || fromRef
}

/** A conversation-open command's optional turn landing: `ui_event.turn_id`
 *  (+ `ui_event.role` picking the user/assistant side). Emitted by the
 *  undocked search window's "bring me here"; absent on plain opens. */
export interface ConversationTurnTarget {
  turnId: string
  role: string | null
}

/**
 * The turn a conversation-open surface command asks to land on, or null for
 * a plain open. Callers gate on `conversationIdFromSurfaceCommand` first —
 * this only reads the refinement fields.
 */
export function turnTargetFromSurfaceCommand(data: Record<string, unknown>): ConversationTurnTarget | null {
  const uiEvent = recordValue(data.ui_event)
  const turnId = stringValue(uiEvent.turn_id) || stringValue(data.turn_id)
  if (!turnId) return null
  const role = stringValue(uiEvent.role) || stringValue(data.role)
  return { turnId, role: role || null }
}

/**
 * Conversation id a chat surface command asks to open, or '' when the message
 * is not a conversation-open command for this widget.
 */
export function conversationIdFromSurfaceCommand(data: Record<string, unknown>): string {
  const target = stringValue(data.target_surface).toLowerCase()
  const action = stringValue(data.action).toLowerCase()
  if (
    data.type !== SURFACE_COMMAND_MESSAGE_TYPE ||
    !CHAT_CONVERSATION_SURFACES.has(target) ||
    !CONVERSATION_OPEN_ACTIONS.has(action)
  ) return ''
  const uiEvent = recordValue(data.ui_event)
  const context = recordValue(data.context)
  const contextData = recordValue(context.data)
  const direct = stringValue(data.conversation_id) ||
    stringValue(uiEvent.conversation_id) ||
    stringValue(contextData.conversation_id) ||
    stringValue(context.conversation_id)
  if (direct) return direct
  const ref = stringValue(data.object_ref) ||
    stringValue(uiEvent.object_ref) ||
    stringValue(context.object_ref) ||
    stringValue(context.ref) ||
    stringValue(context.logical_path)
  return conversationIdFromConversationRef(ref)
}
