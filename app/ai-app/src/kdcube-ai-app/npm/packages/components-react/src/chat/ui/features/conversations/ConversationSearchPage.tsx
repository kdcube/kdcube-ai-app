/**
 * Full-page conversation search — the served-widget presentation of the SAME
 * search surface the chat sidebar drives (one controls + results body, its
 * own shell). The undocked scene window renders this page; a
 * `conversation_search.open` seed arrives via the `seed` prop (already
 * parsed by the widget) and is applied through the vm, optionally
 * auto-running. Hits navigate OUTWARD: the callbacks emit the
 * `sdk.chat.conversation` open back to the host, they never load a
 * conversation here — this window has no transcript.
 */

import { useEffect } from 'react'
import type {
  ConversationSearchHit,
  ConversationSearchParams,
  ConversationSearchResponse,
} from '@kdcube/components-core/chat'
import {
  useConversationSearch,
  type ConversationSearchSeed,
} from './useConversationSearch.ts'
import { ConversationSearchControls } from './ConversationSearchControls.tsx'
import { ConversationSearchResults } from './ConversationSearchResults.tsx'

export function ConversationSearchPage({
  search,
  activeConversationId = null,
  seed = null,
  onOpenConversation,
  onJumpToHit,
  title = 'Search chats',
  subtitle,
  notice,
}: {
  search: (request: ConversationSearchParams) => Promise<ConversationSearchResponse>
  /** The chat's open conversation (from the seed) — enables the "This chat"
   *  scope. Absent = deep search across all chats only. */
  activeConversationId?: string | null
  /** Latest `conversation_search.open` seed; `nonce` re-applies a re-summon
   *  of an already-open window. */
  seed?: { payload: ConversationSearchSeed; nonce: number } | null
  onOpenConversation: (conversationId: string) => void
  onJumpToHit: (hit: ConversationSearchHit, role?: string | null) => void
  title?: string
  subtitle?: string
  /** Transient status line under the head (e.g. "couldn't reach the chat"). */
  notice?: string | null
}) {
  const vm = useConversationSearch({
    search,
    activeConversationId,
    initialScope: 'all',
  })

  const applySeed = vm.applySeed
  useEffect(() => {
    if (seed) applySeed(seed.payload)
  }, [seed, applySeed])

  return (
    <div className="kcs-page">
      <div className="kcs-page-head">
        <div className="kcs-page-title">{title}</div>
        {subtitle ? <div className="kcs-page-sub">{subtitle}</div> : null}
      </div>
      {notice ? <div className="kcs-page-notice" role="status">{notice}</div> : null}
      <div className="kcs-page-body">
        <ConversationSearchControls
          vm={vm}
          disabled={false}
          availableScopes={activeConversationId ? ['current', 'all'] : ['all']}
        />
        {vm.mode === 'results' ? (
          <ConversationSearchResults
            vm={vm}
            onOpenConversation={onOpenConversation}
            onJumpToHit={onJumpToHit}
            backLabel="Clear"
          />
        ) : (
          <div className="kcs-empty">
            Search your chats — words, a time range, or both. Results open in the chat window.
          </div>
        )}
      </div>
    </div>
  )
}
