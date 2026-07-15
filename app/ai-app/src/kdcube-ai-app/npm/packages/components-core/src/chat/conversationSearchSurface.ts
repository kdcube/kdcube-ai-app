/**
 * `conversation_search.open` — the scene surface-command contract for the
 * undocked conversation-search window, mirroring `capabilities.open`.
 *
 * EMIT (the chat search pane's undock affordance): post a
 * `kdcube.surface.command` to the parent frame targeting `sdk.chat.search`
 * with the CURRENT search state as the seed and await the host's
 * `{command_id, ok}` ack. An acked command means the search opened as a real
 * scene window (resizable/dockable like every widget); a timeout or
 * standalone context keeps the in-chat presentation.
 *
 * RECEIVE (the served `conversation_search` widget): parse the routed
 * command, apply the seed at runtime (query, scope, kinds, time range, rank
 * weights), run the search when `autorun`, and ack for host diagnostics.
 *
 * The reverse direction — "bring me here" from the undocked window back into
 * the chat — is the EXISTING `sdk.chat.conversation` open contract carrying
 * `conversation_id` (+ the `turn_id`/`role` jump refinement), emitted via
 * `openSurfaceOnHost`.
 */

import {
  SURFACE_COMMAND_MESSAGE_TYPE,
  SURFACE_COMMAND_ACK_MESSAGE_TYPE,
  openSurfaceOnHost,
} from './capabilitiesSurface.ts'

export const CONVERSATION_SEARCH_SURFACE = 'sdk.chat.search'

/** Seed payload of one `conversation_search.open` (the command's `ui_event`).
 *  Everything optional: an empty seed opens the window on a blank search. */
export interface ConversationSearchOpenPayload {
  query?: string
  /** Deep scopes only — the standalone window has no local title list. */
  scope?: 'current' | 'all'
  /** The open conversation, required by `scope: 'current'`. */
  conversation_id?: string
  /** Agent binding of the emitting chat (multi-agent apps search their own
   *  agent's conversations; absent = the bundle default). */
  agent_id?: string
  /** HOW kinds: user | assistant | summary. */
  targets?: string[]
  /** WHEN row: any | 7 | 30 | 90 | custom. */
  time_preset?: string
  /** Custom range bounds (YYYY-MM-DD), with `time_preset: 'custom'`. */
  date_from?: string
  date_to?: string
  /** RANK arms (0..2 sliders). */
  weights?: { semantic?: number; lexical?: number; recency?: number }
  /** Run the seeded search immediately on arrival. */
  autorun?: boolean
}

export interface ConversationSearchOpenCommand {
  targetSurface: string
  commandId: string
  payload: ConversationSearchOpenPayload
}

/** Ask the HOST to open the conversation search as a scene window. Same ack
 *  semantics as `openCapabilitiesOnHost`: resolves true only on an explicit
 *  positive ack, so the caller keeps its in-chat presentation on false.
 *  Never throws. */
export function openConversationSearchOnHost(
  payload: ConversationSearchOpenPayload = {},
  options: { source?: string; widget?: string; timeoutMs?: number } = {},
): Promise<boolean> {
  const ui_event: Record<string, unknown> = {}
  const query = String(payload.query || '').trim()
  if (query) ui_event.query = query
  const scope = payload.scope === 'current' || payload.scope === 'all' ? payload.scope : ''
  if (scope) ui_event.scope = scope
  const conversation = String(payload.conversation_id || '').trim()
  if (conversation) ui_event.conversation_id = conversation
  const agent = String(payload.agent_id || '').trim()
  if (agent) ui_event.agent_id = agent
  const targets = (payload.targets ?? []).map((item) => String(item || '').trim()).filter(Boolean)
  if (targets.length) ui_event.targets = targets
  const preset = String(payload.time_preset || '').trim()
  if (preset) ui_event.time_preset = preset
  const dateFrom = String(payload.date_from || '').trim()
  if (dateFrom) ui_event.date_from = dateFrom
  const dateTo = String(payload.date_to || '').trim()
  if (dateTo) ui_event.date_to = dateTo
  if (payload.weights && typeof payload.weights === 'object') {
    const weights: Record<string, number> = {}
    for (const arm of ['semantic', 'lexical', 'recency'] as const) {
      const value = payload.weights[arm]
      if (typeof value === 'number' && Number.isFinite(value)) weights[arm] = value
    }
    if (Object.keys(weights).length) ui_event.weights = weights
  }
  if (payload.autorun) ui_event.autorun = true
  return openSurfaceOnHost(CONVERSATION_SEARCH_SURFACE, ui_event, {
    source: options.source || 'chat-search',
    ...(options.widget ? { widget: options.widget } : {}),
    ...(options.timeoutMs !== undefined ? { timeoutMs: options.timeoutMs } : {}),
  })
}

/** The chat widget's conversation surface (its `targetSurfaces` entry) — the
 *  "bring me here" target of hits in the undocked window. */
export const CHAT_CONVERSATION_SURFACE = 'sdk.chat.conversation'

/** Ask the HOST to open a conversation in the chat window — optionally landing
 *  on one turn (`turn_id`, with `role` picking the user/assistant side).
 *  Resolves true only on a positive ack (the scene routed it into a chat
 *  surface); the standalone widget shows its "no chat around" notice on false.
 *  Never throws. */
export function openConversationInChatOnHost(
  target: { conversation_id: string; turn_id?: string; role?: string | null },
  options: { source?: string; widget?: string; timeoutMs?: number } = {},
): Promise<boolean> {
  const conversation = String(target.conversation_id || '').trim()
  if (!conversation) return Promise.resolve(false)
  const ui_event: Record<string, unknown> = { conversation_id: conversation }
  const turn = String(target.turn_id || '').trim()
  if (turn) ui_event.turn_id = turn
  const role = String(target.role || '').trim()
  if (role) ui_event.role = role
  return openSurfaceOnHost(CHAT_CONVERSATION_SURFACE, ui_event, {
    source: options.source || 'conversation-search',
    ...(options.widget ? { widget: options.widget } : {}),
    ...(options.timeoutMs !== undefined ? { timeoutMs: options.timeoutMs } : {}),
  })
}

/** Parse a routed `conversation_search.open` surface command (widget side). */
export function parseConversationSearchOpen(data: unknown): ConversationSearchOpenCommand | null {
  if (!data || typeof data !== 'object') return null
  const raw = data as Record<string, unknown>
  if (raw.type !== SURFACE_COMMAND_MESSAGE_TYPE) return null
  const target = typeof raw.target_surface === 'string' ? raw.target_surface.trim().toLowerCase() : ''
  if (target !== CONVERSATION_SEARCH_SURFACE) return null
  const action = typeof raw.action === 'string' ? raw.action.trim().toLowerCase() : ''
  if (action && action !== 'open') return null
  const source = (raw.ui_event && typeof raw.ui_event === 'object' ? raw.ui_event : {}) as Record<string, unknown>
  const payload: ConversationSearchOpenPayload = {}
  const query = typeof source.query === 'string' ? source.query.trim() : ''
  if (query) payload.query = query
  const scope = typeof source.scope === 'string' ? source.scope.trim().toLowerCase() : ''
  if (scope === 'current' || scope === 'all') payload.scope = scope
  const conversation = typeof source.conversation_id === 'string' ? source.conversation_id.trim() : ''
  if (conversation) payload.conversation_id = conversation
  const agent = typeof source.agent_id === 'string' ? source.agent_id.trim() : ''
  if (agent) payload.agent_id = agent
  if (Array.isArray(source.targets)) {
    const targets = source.targets.map((item) => String(item || '').trim()).filter(Boolean)
    if (targets.length) payload.targets = targets
  }
  const preset = typeof source.time_preset === 'string' ? source.time_preset.trim() : ''
  if (preset) payload.time_preset = preset
  const dateFrom = typeof source.date_from === 'string' ? source.date_from.trim() : ''
  if (dateFrom) payload.date_from = dateFrom
  const dateTo = typeof source.date_to === 'string' ? source.date_to.trim() : ''
  if (dateTo) payload.date_to = dateTo
  if (source.weights && typeof source.weights === 'object') {
    const raw = source.weights as Record<string, unknown>
    const weights: ConversationSearchOpenPayload['weights'] = {}
    for (const arm of ['semantic', 'lexical', 'recency'] as const) {
      const value = Number(raw[arm])
      if (Number.isFinite(value)) weights[arm] = value
    }
    if (Object.keys(weights).length) payload.weights = weights
  }
  if (source.autorun === true) payload.autorun = true
  return {
    targetSurface: target,
    commandId: typeof raw.command_id === 'string' ? raw.command_id.trim() : '',
    payload,
  }
}

/** Widget-side diagnostics ack (the scene host acks the emitter itself). */
export function ackConversationSearchOpen(command: ConversationSearchOpenCommand, reason: string): void {
  try {
    if (typeof window === 'undefined' || !window.parent || window.parent === window) return
    const ack: Record<string, unknown> = {
      type: SURFACE_COMMAND_ACK_MESSAGE_TYPE,
      target_surface: command.targetSurface,
      action: 'open',
      reason,
      ts: new Date().toISOString(),
    }
    if (command.commandId) {
      ack.command_id = command.commandId
      ack.ok = true
    }
    window.parent.postMessage(ack, '*')
  } catch {
    /* host diagnostics are best-effort only */
  }
}
