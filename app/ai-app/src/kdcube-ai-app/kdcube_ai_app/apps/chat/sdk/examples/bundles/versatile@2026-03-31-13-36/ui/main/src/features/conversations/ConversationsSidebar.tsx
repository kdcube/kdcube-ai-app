/** Left-hand chat list. Moved verbatim from App.tsx (Wave 2). */
import type { ConversationSummary } from '../../service.ts'
import { formatConversationTime } from '../../components/utils.ts'

export function ConversationsSidebar({
  conversations,
  query,
  activeConversationId,
  disabled,
  loading,
  error,
  loadingConversationId,
  onQueryChange,
  onRefresh,
  onSelect,
  onStartNew,
}: {
  conversations: ConversationSummary[]
  query: string
  activeConversationId: string | null
  disabled: boolean
  loading: boolean
  error: string | null
  loadingConversationId: string | null
  onQueryChange: (value: string) => void
  onRefresh: () => void
  onSelect: (conversationId: string) => void
  onStartNew: () => void
}) {
  return (
    <aside className="glass-panel flex min-h-[520px] flex-col overflow-hidden lg:sticky lg:top-4">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--line-soft)] px-3 py-2">
        <div className="min-w-0">
          <div className="text-[13px] font-semibold text-[var(--ink)]">Chats</div>
          <div className="text-[11px] text-[var(--muted)]">Bundle conversations</div>
        </div>
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

      <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--line-soft)]">
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search chats"
          disabled={disabled}
          className="k-input"
        />
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
      </div>

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
          {query.trim()
            ? 'No chats match the current search.'
            : 'No saved chats yet. Start a new one and it will appear here.'}
        </p>
      ) : null}

      {conversations.length > 0 ? (
        <div className="k-rows min-w-0 flex-1 overflow-auto">
          {conversations.map((conversation) => {
            const isActive = conversation.id === activeConversationId
            const isLoading = loadingConversationId === conversation.id
            return (
              <button
                key={conversation.id}
                type="button"
                onClick={() => onSelect(conversation.id)}
                disabled={disabled || isLoading}
                className={`k-row ${isActive ? 'k-active' : ''}`}
              >
                <div className="k-row-main">
                  <div className="k-row-title">
                    {conversation.title || 'Untitled conversation'}
                  </div>
                  <div className="k-row-sub">
                    {formatConversationTime(conversation.lastActivityAt || conversation.startedAt)}
                    {isLoading ? ' · loading…' : ''}
                  </div>
                </div>
                {isActive ? <span className="k-chip k-teal">open</span> : null}
              </button>
            )
          })}
        </div>
      ) : null}
    </aside>
  )
}
