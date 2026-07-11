/**
 * Search / browse results in the sidebar — replaces the chat list while active.
 *
 * Hits are grouped by conversation (header = title + match count, click opens
 * the conversation). A hit (one turn) renders ONE CARD PER SNIPPET, so each
 * snippet's role is unmistakable — a gold `summary` chip is instantly tellable
 * from a teal `assistant` one. Every card is a "bring me here" button whose
 * target is the TURN: kind chip (from the snippet's own role, falling back to
 * `matched_via_role`), an optional "best match" pill on the top-relevance
 * card, the shared "turn N of M · full timestamp", a 3-line clamped snippet
 * with `<mark>` term highlighting, and a gentle relevance whisper (34px bar
 * + %). Sort-by relevance|time reorders the same hits locally. Browse mode
 * (blank query + time range) renders the turns chronologically without
 * relevance.
 */
import { useMemo } from 'react'
import type { ConversationSearchHit } from '@kdcube/components-core/chat'
import {
  buildHighlightSegments,
  conversationSearchHitKey,
  groupHitsByConversation,
  relativeRelevance,
} from '@kdcube/components-core/chat'
import type { ConversationSearchGroup } from '@kdcube/components-core/chat'
import type { ConversationSearchSort, ConversationSearchVm } from './useConversationSearch.ts'

/** Kind pill visuals per snippet role ('user' reads as "you"). */
function kindPill(role: string | null | undefined): { label: string; tint: string } {
  switch ((role || '').toLowerCase()) {
    case 'assistant':
      return { label: 'assistant', tint: 'kcs-assistant' }
    case 'summary':
      return { label: 'summary', tint: 'kcs-summary' }
    case 'attachment':
      return { label: 'attachment', tint: 'kcs-attachment' }
    default:
      return { label: 'you', tint: 'kcs-you' }
  }
}

/** Full hit timestamp, e.g. "Jul 10, 05:28 PM". */
function formatHitTimestamp(ts?: string | null): string {
  if (!ts) return ''
  const date = new Date(ts)
  if (Number.isNaN(date.getTime())) return ''
  const month = date.toLocaleString([], { month: 'short' })
  let hours = date.getHours()
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const meridiem = hours >= 12 ? 'PM' : 'AM'
  hours = hours % 12 || 12
  return `${month} ${date.getDate()}, ${String(hours).padStart(2, '0')}:${minutes} ${meridiem}`
}

function hitTimeValue(hit: ConversationSearchHit): number {
  const parsed = hit.ts ? Date.parse(hit.ts) : NaN
  return Number.isFinite(parsed) ? parsed : 0
}

function bestGroupScore(group: ConversationSearchGroup): number {
  let best = 0
  for (const hit of group.hits) {
    if (typeof hit.score === 'number' && hit.score > best) best = hit.score
  }
  return best
}

/** Group + order the hits for display. Relevance keeps the server's ranked
 *  order inside each group; time re-sorts newest-first on both levels. */
function orderGroups(hits: ConversationSearchHit[], sort: ConversationSearchSort): ConversationSearchGroup[] {
  const groups = groupHitsByConversation(hits)
  if (sort === 'ts') {
    const sorted = groups.map((group) => ({
      ...group,
      hits: [...group.hits].sort((left, right) => hitTimeValue(right) - hitTimeValue(left)),
    }))
    sorted.sort((left, right) => hitTimeValue(right.hits[0]) - hitTimeValue(left.hits[0]))
    return sorted
  }
  return [...groups].sort((left, right) => bestGroupScore(right) - bestGroupScore(left))
}

/** One rendered result card = one snippet of one hit (the jump target stays
 *  the hit's turn). */
interface HitCard {
  key: string
  hit: ConversationSearchHit
  role: string | null
  text: string
  /** True on the card whose role is the one the hit actually matched via —
   *  the card that wears the "best match" pill when its hit is the top hit. */
  primary: boolean
}

/** Expand a hit into per-snippet cards. Snippets with neither text nor role
 *  are dropped; a hit whose snippets are all empty still yields one placeholder
 *  card so the match stays reachable. */
function cardsForHit(hit: ConversationSearchHit): HitCard[] {
  const hitKey = conversationSearchHitKey(hit)
  const matchedRole = (hit.matched_via_role || '').trim() || null
  const usable = (hit.snippets || [])
    .map((snippet) => ({
      role: (snippet.role || '').trim() || null,
      text: (snippet.text || '').trim(),
    }))
    .filter((snippet) => snippet.text || snippet.role)
  if (usable.length === 0) {
    return [{ key: `${hitKey}:0`, hit, role: matchedRole, text: '', primary: true }]
  }
  const primaryIndex = matchedRole
    ? Math.max(0, usable.findIndex((snippet) => snippet.role === matchedRole))
    : 0
  return usable.map((snippet, index) => ({
    key: `${hitKey}:${index}`,
    hit,
    role: snippet.role ?? matchedRole,
    text: snippet.text,
    primary: index === primaryIndex,
  }))
}

function HitText({ text, query }: { text: string; query: string }) {
  const segments = useMemo(() => buildHighlightSegments(text, query), [text, query])
  return (
    <span className="kcs-hit-text">
      {segments.map((segment, index) =>
        segment.match ? <mark key={index}>{segment.text}</mark> : <span key={index}>{segment.text}</span>,
      )}
    </span>
  )
}

export function ConversationSearchResults({
  vm,
  onOpenConversation,
  onJumpToHit,
}: {
  vm: ConversationSearchVm
  onOpenConversation: (conversationId: string) => void
  onJumpToHit: (hit: ConversationSearchHit) => void
}) {
  const hits = vm.response?.hits ?? []
  const conversations = vm.response?.conversations ?? {}
  const warnings = vm.response?.warnings ?? []

  const groups = useMemo(() => orderGroups(hits, vm.sort), [hits, vm.sort])
  const relevance = useMemo(() => relativeRelevance(hits), [hits])
  /* BEST MATCH is always the top-relevance hit, whatever the display sort;
   * within that hit it sits on the primary (matched-role) card. */
  const bestHitKey = useMemo(() => {
    if (vm.browse) return null
    let best: ConversationSearchHit | null = null
    for (const hit of hits) {
      if (typeof hit.score !== 'number') continue
      if (!best || (best.score ?? 0) < hit.score) best = hit
    }
    return best ? conversationSearchHitKey(best) : null
  }, [hits, vm.browse])

  const backLink = (
    <button type="button" className="kcs-link" onClick={vm.clearSearch}>
      back to chats
    </button>
  )

  if (hits.length === 0) {
    return (
      <div className="kcs-results">
        <div className="kcs-meta">
          0 matches{vm.resultsQuery ? <> for "{vm.resultsQuery}"</> : null} · {backLink}
        </div>
        <div className="kcs-empty">
          Nothing matched{vm.browse || vm.resultsQuery ? ' in this time range' : ''}. Try fewer words or a wider
          range.
        </div>
      </div>
    )
  }

  return (
    <div className="kcs-results">
      {vm.browse ? (
        <div className="kcs-meta">
          <b>{hits.length}</b> turn{hits.length > 1 ? 's' : ''} in <b>{groups.length}</b> conversation
          {groups.length > 1 ? 's' : ''} in this time range, newest first · {backLink}
        </div>
      ) : (
        <div className="kcs-meta">
          <b>{hits.length}</b> match{hits.length > 1 ? 'es' : ''} in <b>{groups.length}</b> conversation
          {groups.length > 1 ? 's' : ''}
          {warnings.map((warning) => (
            <span key={warning}> · {warning}</span>
          ))}{' '}
          · {backLink}
          <br />
          <span className="kcs-sort">
            sort by{' '}
            <button
              type="button"
              className={`kcs-link ${vm.sort === 'rel' ? 'kcs-on' : ''}`}
              onClick={() => vm.setSort('rel')}
            >
              relevance
            </button>{' '}
            ·{' '}
            <button
              type="button"
              className={`kcs-link ${vm.sort === 'ts' ? 'kcs-on' : ''}`}
              onClick={() => vm.setSort('ts')}
            >
              time
            </button>
          </span>
        </div>
      )}

      {groups.map((group) => {
        const meta = conversations[group.conversationId]
        return (
          <div key={group.conversationId} className="kcs-grp">
            <button
              type="button"
              className="kcs-grp-head"
              onClick={() => onOpenConversation(group.conversationId)}
              title="Open this conversation"
            >
              <span className="kcs-grp-title">{meta?.title || 'Untitled conversation'}</span>
              <span className="kcs-grp-sub">
                {group.hits.length} match{group.hits.length > 1 ? 'es' : ''}
              </span>
            </button>
            {group.hits.flatMap(cardsForHit).map((card) => {
              const hit = card.hit
              const pill = kindPill(card.role)
              const rel = relevance.get(hit) ?? null
              const when = formatHitTimestamp(hit.ts)
              const position =
                hit.ordinal != null && hit.total_turns != null
                  ? `turn ${hit.ordinal} of ${hit.total_turns}${when ? ` · ${when}` : ''}`
                  : when
              const isBest = card.primary && conversationSearchHitKey(hit) === bestHitKey
              return (
                <button
                  key={card.key}
                  type="button"
                  className={`kcs-hit ${vm.visitedKey === card.key ? 'kcs-visited' : ''}`}
                  onClick={() => {
                    vm.markVisited(card.key)
                    onJumpToHit(hit)
                  }}
                  title="Bring me here"
                >
                  <span className="kcs-hit-top">
                    <span className={`kcs-kind ${pill.tint}`}>{pill.label}</span>
                    {isBest ? <span className="kcs-best">best match</span> : null}
                    {position ? <span className="kcs-hit-pos">{position}</span> : null}
                  </span>
                  {!card.text ? (
                    /* Defensive: a hit whose snippets are all empty still shows
                     * as a navigable card, with a muted placeholder line. */
                    <span className="kcs-hit-text kcs-hit-text-empty">— no preview —</span>
                  ) : vm.browse ? (
                    <span className="kcs-hit-text">{card.text}</span>
                  ) : (
                    <HitText text={card.text} query={vm.resultsQuery} />
                  )}
                  {rel != null ? (
                    <span className="kcs-rel">
                      <span className="kcs-rel-bar">
                        <span className="kcs-rel-fill" style={{ width: `${rel}%` }} />
                      </span>
                      <span className="kcs-rel-num">{rel}%</span>
                    </span>
                  ) : null}
                </button>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
