/** Left-hand chat list + conversation search.
 *
 *  Each row is the conversation summary as a `<button>` (load on click). On
 *  hover or focus the row reveals a trash icon that calls `onDelete` —
 *  parents are responsible for confirming with the user before invoking
 *  the irreversible backend delete. Refresh and new-chat live in the header
 *  bar; the search controls sit under it.
 *
 *  Search has two personalities (see `useConversationSearch`): the `titles`
 *  scope filters this list locally as the user types (the parent passes the
 *  already-filtered `conversations`), while the deep scopes call the backend
 *  on Search and swap the list for `<ConversationSearchResults/>` until the
 *  user clears back.
 */

import { memo, useEffect, useState } from 'react'
import type { ConversationSearchHit, ConversationSummary } from '@kdcube/components-core/chat'
import { formatConversationTime } from '../../support/utils.ts'
import type { ConversationSearchVm } from './useConversationSearch.ts'
import { ConversationSearchControls } from './ConversationSearchControls.tsx'
import { ConversationSearchResults } from './ConversationSearchResults.tsx'

/* Render only the most recent N (the list is sorted newest-first by the
 * parent); a "Load more" control reveals older ones in the same-size pages.
 * Keeps the list short and the DOM light when a user has many conversations. */
const PAGE_SIZE = 20

function ConversationsSidebarImpl({
  conversations,
  search,
  activeConversationId,
  disabled,
  loading,
  error,
  loadingConversationId,
  deletingConversationId,
  onRefresh,
  onSelect,
  onStartNew,
  onDelete,
  onJumpToHit,
  onUndockSearch,
}: {
  conversations: ConversationSummary[]
  search: ConversationSearchVm
  activeConversationId: string | null
  disabled: boolean
  loading: boolean
  error: string | null
  loadingConversationId: string | null
  deletingConversationId: string | null
  onRefresh: () => void
  onSelect: (conversationId: string) => void
  onStartNew: () => void
  onDelete: (conversation: ConversationSummary) => void
  onJumpToHit: (hit: ConversationSearchHit, role?: string | null) => void
  /** Present = search results offer "open as a window" (see
   *  `ConversationSearchResults.onUndock`). */
  onUndockSearch?: () => void
}) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)
  /* Reset the window when the title filter changes so results start from the
   * top of the (re)filtered list. */
  useEffect(() => {
    setVisibleCount(PAGE_SIZE)
  }, [search.query])
  const visible = conversations.slice(0, visibleCount)
  const remaining = conversations.length - visible.length

  const resultsMode = search.mode === 'results'
  const titleFilterActive = search.scope === 'titles' && Boolean(search.query.trim())

  return (
    <aside className="glass-panel flex min-h-0 flex-col overflow-hidden lg:h-full">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--line-soft)] px-3 py-2">
        <div className="min-w-0">
          <div className="text-[13px] font-semibold text-[var(--ink)]">
            {resultsMode ? (search.browse ? 'Browse' : 'Results') : 'Chats'}
          </div>
          <div className="truncate text-[11px] text-[var(--muted)]">
            {resultsMode
              ? search.browse
                ? 'by time range'
                : `for "${search.resultsQuery}"`
              : 'Bundle conversations'}
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={onRefresh}
            className="k-iconbtn"
            aria-label="Refresh"
            title="Refresh"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12a9 9 0 1 1-3-6.7" />
              <path d="M21 3v6h-6" />
            </svg>
          </button>
          <button
            type="button"
            onClick={onStartNew}
            disabled={disabled}
            className="k-iconbtn"
            aria-label="New chat"
            title="New chat"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>
        </div>
      </div>

      <ConversationSearchControls vm={search} disabled={disabled} />

      {resultsMode ? (
        <ConversationSearchResults vm={search} onOpenConversation={onSelect} onJumpToHit={onJumpToHit} onUndock={onUndockSearch} />
      ) : (
        <>
          {error ? (
            <div className="px-3 pt-3">
              <div className="k-notice k-error">
                <span>{error}</span>
              </div>
            </div>
          ) : null}

          {loading && conversations.length === 0 ? (
            <p className="px-3 py-3 text-[12px] text-[var(--muted)]">Loading conversations…</p>
          ) : null}

          {!loading && conversations.length === 0 ? (
            <p className="px-3 py-3 text-[12px] leading-5 text-[var(--muted)]">
              {titleFilterActive
                ? 'No chats match the current search.'
                : 'No saved chats yet. Start a new one and it will appear here.'}
            </p>
          ) : null}

          {conversations.length > 0 ? (
            <div className="k-rows min-w-0 flex-1 overflow-auto">
              {visible.map((conversation) => {
                const isActive = conversation.id === activeConversationId
                const isLoading = loadingConversationId === conversation.id
                const isDeleting = deletingConversationId === conversation.id
                /* The row uses position:relative; the delete affordance is
                   absolutely positioned at the right edge so the underlying
                   <button> stays the click target for the whole row.
                   We render a sibling button rather than nesting one inside
                   the row <button> (invalid HTML). */
                return (
                  <div key={conversation.id} className="k-row-shell">
                    <button
                      type="button"
                      onClick={() => onSelect(conversation.id)}
                      disabled={disabled || isLoading || isDeleting}
                      className={`k-row ${isActive ? 'k-active' : ''}`}
                    >
                      <div className="k-row-main">
                        <div className="k-row-title">
                          {conversation.title || 'Untitled conversation'}
                        </div>
                        <div className="k-row-sub">
                          {formatConversationTime(conversation.lastActivityAt || conversation.startedAt)}
                          {isLoading ? ' · loading…' : ''}
                          {isDeleting ? ' · deleting…' : ''}
                        </div>
                      </div>
                      {isActive ? <span className="k-chip k-teal">open</span> : null}
                    </button>
                    <button
                      type="button"
                      className="k-row-delete"
                      aria-label="Delete conversation"
                      title="Delete conversation"
                      disabled={disabled || isLoading || isDeleting}
                      onClick={(event) => {
                        event.preventDefault()
                        event.stopPropagation()
                        onDelete(conversation)
                      }}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6" />
                      </svg>
                    </button>
                  </div>
                )
              })}
              {remaining > 0 ? (
                <div className="px-3 py-2">
                  <button
                    type="button"
                    className="k-btn k-sm k-ghost w-full"
                    onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}
                    disabled={disabled}
                  >
                    Load more · {remaining} older
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
        </>
      )}
    </aside>
  )
}

export const ConversationsSidebar = memo(ConversationsSidebarImpl)
