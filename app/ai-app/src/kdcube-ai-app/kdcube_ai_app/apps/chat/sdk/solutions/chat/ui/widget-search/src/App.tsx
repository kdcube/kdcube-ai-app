/**
 * Full-page conversation search — the served-widget presentation of the SAME
 * search surface the chat sidebar drives (one controls + results body, its
 * own scene window). Data goes straight to the platform conversation-search
 * endpoint with the widget handshake's auth; hits navigate OUTWARD through
 * the host: "bring me here" emits the `sdk.chat.conversation` open (with the
 * `turn_id`/`role` jump refinement) that the scene routes into the chat
 * window — this window has no transcript of its own.
 */

import { useEffect, useRef, useState } from 'react'
import { ConversationSearchPage } from '@kdcube/components-react/chat'
import type { ConversationSearchSeed } from '@kdcube/components-react/chat'
import {
  ackConversationSearchOpen,
  openConversationInChatOnHost,
  parseConversationSearchOpen,
} from '@kdcube/components-core/chat'
import type {
  ConversationSearchHit,
  ConversationSearchOpenPayload,
  ConversationSearchParams,
  ConversationSearchResponse,
  ConversationSearchTarget,
} from '@kdcube/components-core/chat'
import { settings } from './settings.ts'

/** The wire seed (`ui_event`) as the vm's seed shape. Field validation lives
 *  in `applySeed`; this only maps names. */
function seedFromPayload(payload: ConversationSearchOpenPayload): ConversationSearchSeed {
  return {
    ...(payload.query !== undefined ? { query: payload.query } : {}),
    ...(payload.scope ? { scope: payload.scope } : {}),
    ...(payload.targets ? { targets: payload.targets as ConversationSearchTarget[] } : {}),
    ...(payload.time_preset ? { timePreset: payload.time_preset as ConversationSearchSeed['timePreset'] } : {}),
    ...(payload.date_from !== undefined ? { dateFrom: payload.date_from } : {}),
    ...(payload.date_to !== undefined ? { dateTo: payload.date_to } : {}),
    ...(payload.weights ? { weights: payload.weights } : {}),
    ...(payload.autorun ? { autorun: true } : {}),
  }
}

async function searchConversations(
  params: ConversationSearchParams,
  agentId: string,
): Promise<ConversationSearchResponse> {
  const body: Record<string, unknown> = { ...params, bundle_id: settings.getBundleId() }
  // Explicit binding only — the backend matches agent_id exactly, and an
  // unbound chat's conversations store a NULL agent (see settings.getAgentId).
  if (agentId) body.agent_id = agentId
  for (const key of Object.keys(body)) {
    if (body[key] === null || body[key] === undefined) delete body[key]
  }
  const response = await fetch(
    `${settings.getBaseUrl()}/api/cb/conversations/` +
    `${encodeURIComponent(settings.getTenant())}/${encodeURIComponent(settings.getProject())}/search`,
    {
      method: 'POST',
      credentials: 'include',
      headers: settings.authHeaders({ 'Content-Type': 'application/json', Accept: 'application/json' }),
      body: JSON.stringify(body),
    },
  )
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText)
    throw new Error(`Search failed (${response.status}): ${detail}`)
  }
  const data = (await response.json()) as ConversationSearchResponse
  return {
    ...data,
    hits: Array.isArray(data.hits) ? data.hits : [],
    conversations: data.conversations && typeof data.conversations === 'object' ? data.conversations : {},
  }
}

function SearchApp() {
  // Scene hosts summon this widget with a `conversation_search.open` surface
  // command whose ui_event seeds the search (query, scope, kinds, time
  // range, rank weights) and optionally auto-runs it. A chat-originated open
  // carries the chat's conversation id (enables the "This chat" scope) and
  // its explicit agent binding.
  const [agentId, setAgentId] = useState(settings.getAgentId())
  const [conversationId, setConversationId] = useState('')
  const [seed, setSeed] = useState<{ payload: ConversationSearchSeed; nonce: number } | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const agentRef = useRef(agentId)
  agentRef.current = agentId
  const noticeTimer = useRef<number | null>(null)

  useEffect(() => {
    const onSurfaceCommand = (event: MessageEvent) => {
      const command = parseConversationSearchOpen(event.data)
      if (!command) return
      const payload = command.payload
      if (payload.agent_id !== undefined) {
        agentRef.current = payload.agent_id
        setAgentId(payload.agent_id)
      }
      setConversationId(payload.conversation_id ?? '')
      setSeed({ payload: seedFromPayload(payload), nonce: Date.now() })
      ackConversationSearchOpen(command, 'applied')
    }
    window.addEventListener('message', onSurfaceCommand)
    return () => window.removeEventListener('message', onSurfaceCommand)
  }, [])

  useEffect(() => () => {
    if (noticeTimer.current !== null) window.clearTimeout(noticeTimer.current)
  }, [])
  const flashNotice = (text: string) => {
    setNotice(text)
    if (noticeTimer.current !== null) window.clearTimeout(noticeTimer.current)
    noticeTimer.current = window.setTimeout(() => setNotice(null), 5000)
  }

  /* Both navigations land in the CHAT window via the host; a false ack means
   * no chat surface answered (e.g. this widget opened as a plain tab). */
  const navigateToChat = (target: { conversation_id: string; turn_id?: string; role?: string | null }) => {
    void openConversationInChatOnHost(target, { source: 'conversation-search-widget', widget: 'conversation_search' })
      .then((acked) => {
        if (!acked) flashNotice('No chat window answered — open this search from the workspace to jump into conversations.')
      })
  }
  const handleOpenConversation = (conversationId: string) => {
    navigateToChat({ conversation_id: conversationId })
  }
  const handleJumpToHit = (hit: ConversationSearchHit, role?: string | null) => {
    navigateToChat({
      conversation_id: hit.conversation_id,
      turn_id: hit.turn_id,
      role: role ?? hit.matched_via_role ?? null,
    })
  }

  return (
    <ConversationSearchPage
      search={(params) => searchConversations(params, agentRef.current)}
      activeConversationId={conversationId || null}
      seed={seed}
      onOpenConversation={handleOpenConversation}
      onJumpToHit={handleJumpToHit}
      title="Search chats"
      subtitle={agentId
        ? `Deep search across your ${agentId} agent conversations.`
        : 'Deep search across your conversations in this app.'}
      notice={notice}
    />
  )
}

export default function App() {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    void settings.setupParentListener().then(() => setReady(true))
  }, [])
  if (!ready) {
    return (
      <div className="kcs-page">
        <div className="kcs-empty">Connecting…</div>
      </div>
    )
  }
  return <SearchApp />
}
