import { useEffect, useMemo, useRef, useState } from 'react'
import {
  downloadBlobAsFile,
  downloadHostedFile,
  downloadResourceByRN,
  fetchConversationById,
  listBundleConversations,
  openChatStream,
  requestConversationStatus,
  submitChatMessage,
} from './service.ts'
import type {
  BaseEnvelope,
  BannerTone,
  ChatCompleteEnvelope,
  ChatDeltaEnvelope,
  ChatErrorEnvelope,
  ChatHistoryItem,
  ChatServiceEnvelope,
  ChatStartEnvelope,
  ChatStepEnvelope,
  ConversationArtifactDTO,
  ConversationDTO,
  ConversationSummary,
  ContinuationKind,
  ConvStatusEnvelope,
  RateLimitPayload,
  StepStatus,
} from './service.ts'
import { BUILT_BUNDLE_ID, createLocalId, settings } from './settings.ts'

// Wave 1 modular extracts — see ./features/chat/chatTypes.ts and ./components/*
import type {
  AdditionalUserMessage,
  Artifact,
  Banner,
  CanvasArtifact,
  ChatState,
  ChatTurn,
  CodeExecArtifact,
  CodeExecContractItem,
  CodeExecStatus,
  ConnectionState,
  FileArtifact,
  LinkArtifact,
  ServiceErrorArtifact,
  TimelineArtifact,
  TimelineEntry,
  TimelineEntryFormat,
  TimelineEntryKind,
  TurnAttachment,
  TurnState,
  TurnStep,
  TurnTab,
  WebFetchArtifact,
  WebFetchItem,
  WebSearchArtifact,
  WebSearchItem,
} from './features/chat/chatTypes.ts'
import { initialState } from './features/chat/chatTypes.ts'
import {
  closeStreamingMarkdown,
  copyToClipboard,
  escapeHtml,
  formatBytes,
  formatConversationTime,
  formatTime,
  markdownPlugins,
  messageForError,
  prettyJson,
  safeJsonParse,
  shortUrl,
  stepTone,
  timestampValue,
  toneClass,
} from './components/utils.ts'
import { HL_BUILTINS, HL_KEYWORDS, highlightCode, inferLanguage } from './components/highlight.ts'
import { MarkdownBlock } from './components/MarkdownBlock.tsx'
import { CaretIcon } from './components/CaretIcon.tsx'
import { CopyButton } from './components/CopyButton.tsx'
import { DownloadButton } from './components/DownloadButton.tsx'
import { Snippet } from './components/Snippet.tsx'
import type { SnippetProps } from './components/Snippet.tsx'
import { CanvasRender, canvasFilename, canvasMime } from './components/CanvasRender.tsx'
import { SuggestedQuestions } from './components/SuggestedQuestions.tsx'

// Wave 2 modular extracts — feature subcomponents
import { BannerStrip } from './features/banners/BannerStrip.tsx'
import { ConversationsSidebar } from './features/conversations/ConversationsSidebar.tsx'
import { Composer } from './features/composer/Composer.tsx'
import { TurnView } from './features/chat/TurnView.tsx'
import {
  ArtifactFeed,
  CanvasPanel,
  DownloadsPanel,
  FollowupMessageBlock,
  LinksPanel,
  MergedOverviewFeed,
  StepList,
  ThinkingBlock,
  TimelineFeed,
  collectTurnLinks,
  mergeOverviewEvents,
  type OverviewEvent,
  type TurnLink,
} from './features/chat/turnTabs.tsx'
import { ChatTurnView } from './features/chat/ChatTurnView.tsx'

/* Types, initialState, markdownPlugins, pure helpers and the syntax
 * highlighter were extracted to:
 *   - ./features/chat/chatTypes.ts
 *   - ./components/utils.ts
 *   - ./components/highlight.ts
 * Imported at the top of this file. */

function addBanner(state: ChatState, tone: BannerTone, text: string): ChatState {
  const trimmed = text.trim()
  if (!trimmed) return state
  if (state.banners.some((banner) => banner.text === trimmed && banner.tone === tone)) {
    return state
  }
  const banners = [{ id: createLocalId('banner'), tone, text: trimmed }, ...state.banners].slice(0, 4)
  return { ...state, banners }
}

function updateTurn(
  state: ChatState,
  turnId: string,
  updater: (turn: ChatTurn) => ChatTurn,
): ChatState {
  const index = state.turns.findIndex((turn) => turn.id === turnId)
  if (index < 0) return state
  const turns = state.turns.slice()
  turns[index] = updater(turns[index])
  return { ...state, turns }
}

function ensureTurn(state: ChatState, turnId: string, createdAt: number, message = ''): ChatState {
  if (state.turns.some((turn) => turn.id === turnId)) return state
  return {
    ...state,
    turns: [
      ...state.turns,
      {
        ...createEmptyTurn(turnId, createdAt, message),
        state: 'running',
      },
    ],
  }
}

function syncConversationFromEnvelope(state: ChatState, env: BaseEnvelope): ChatState {
  const conversationId = env.conversation?.conversation_id
  const turnId = env.conversation?.turn_id
  if (!conversationId || !turnId) return state
  if (!state.turns.some((turn) => turn.id === turnId)) return state
  if (state.conversationId && state.conversationId !== conversationId) return state
  return {
    ...state,
    conversationId,
  }
}

function upsertArtifact<T extends Artifact>(
  artifacts: Artifact[],
  matcher: (artifact: Artifact) => boolean,
  next: T,
): Artifact[] {
  const index = artifacts.findIndex(matcher)
  if (index < 0) return [...artifacts, next]
  const copy = artifacts.slice()
  copy[index] = next
  return copy
}

function upsertTimelineEntry(
  entries: TimelineEntry[],
  matcher: (entry: TimelineEntry) => boolean,
  next: TimelineEntry,
): TimelineEntry[] {
  const index = entries.findIndex(matcher)
  if (index < 0) return [...entries, next]
  const copy = entries.slice()
  copy[index] = next
  return copy
}

/* prettyJson is now imported from ./components/utils.ts */

function buildChatHistory(turns: ChatTurn[]): ChatHistoryItem[] {
  return turns.reduce<ChatHistoryItem[]>((items, turn) => {
    if (!turn.userMessage.trim()) return items
    items.push({
      role: 'user',
      content: turn.userMessage,
      timestamp: new Date(turn.createdAt).toISOString(),
      id: turn.createdAt,
    })
    return items
  }, [])
}

function findActiveTurn(turns: ChatTurn[]): ChatTurn | null {
  for (let index = turns.length - 1; index >= 0; index -= 1) {
    const turn = turns[index]
    if (turn.state === 'pending' || turn.state === 'running') return turn
  }
  return null
}

function fallbackRateLimitMessage(rateLimit: RateLimitPayload | undefined, data: Record<string, unknown>): string {
  const retryAfterSec = rateLimit?.retry_after_sec ?? null
  const reason = typeof data.reason === 'string' ? data.reason : undefined
  if (retryAfterSec && retryAfterSec > 0) {
    const resetText =
      rateLimit?.reset_text ||
      (() => {
        const resetAt = new Date(Date.now() + retryAfterSec * 1000)
        const now = new Date()
        const timeStr = resetAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        const tomorrow = new Date(now)
        tomorrow.setDate(tomorrow.getDate() + 1)
        if (resetAt.toDateString() === now.toDateString()) return `today at ${timeStr}`
        if (resetAt.toDateString() === tomorrow.toDateString()) return `tomorrow at ${timeStr}`
        return `on ${resetAt.toLocaleDateString([], { month: 'long', day: 'numeric' })} at ${timeStr}`
      })()
    return `You've reached your usage limit. Your quota resets ${resetText}.`
  }
  if (reason === 'concurrency' || reason?.includes('concurrent')) {
    return 'Too many requests are running at once. Wait for one to complete and try again.'
  }
  if (reason === 'quota_lock_timeout') {
    return 'Too many requests are being processed right now. Please try again in a moment.'
  }
  if (reason?.includes('token')) {
    return "You've reached your token limit. Try again later or upgrade your plan."
  }
  if (reason?.includes('request')) {
    return "You've reached your request limit. Try again later or upgrade your plan."
  }
  return "You've reached your usage limit. Please try again later."
}

function timelineTitleForMarker(marker: string, fallbackName?: string | null): string {
  switch (marker) {
    case 'answer':
      return 'Assistant answer'
    case 'thinking':
      return 'Reasoning'
    case 'timeline_text':
      return fallbackName || 'Timeline update'
    case 'canvas':
      return fallbackName || 'Canvas update'
    default:
      return fallbackName || 'Stream update'
  }
}

function timelineTitleForSubsystem(subtype: string, fallbackName?: string | null): string {
  switch (subtype) {
    case 'web_search.filtered_results':
      return fallbackName || 'Web search results'
    case 'web_search.html_view':
      return fallbackName || 'Web search report'
    case 'web_fetch.results':
      return fallbackName || 'Web fetch results'
    case 'code_exec.code':
      return fallbackName || 'Exec code'
    case 'code_exec.program.name':
      return fallbackName || 'Exec program name'
    case 'code_exec.objective':
      return fallbackName || 'Exec objective'
    case 'code_exec.contract':
      return fallbackName || 'Exec contract'
    case 'code_exec.status':
      return fallbackName || 'Exec status'
    default:
      return fallbackName || subtype || 'Subsystem update'
  }
}

function extractPayload(record: ConversationArtifactDTO['data']): Record<string, unknown> {
  if (record?.payload && typeof record.payload === 'object') return record.payload
  if (record && typeof record === 'object') return record as Record<string, unknown>
  return {}
}

function normalizeTurnAttachment(
  payload: Record<string, unknown>,
  fallbackId: string,
  file?: File,
): TurnAttachment {
  const meta = payload.meta && typeof payload.meta === 'object' ? (payload.meta as Record<string, unknown>) : {}
  const name =
    (typeof payload.filename === 'string' && payload.filename) ||
    (typeof payload.name === 'string' && payload.name) ||
    (typeof meta.filename === 'string' && meta.filename) ||
    (typeof meta.name === 'string' && meta.name) ||
    file?.name ||
    'attachment'

  return {
    id: fallbackId,
    name,
    size:
      typeof payload.size === 'number'
        ? payload.size
        : typeof payload.size_bytes === 'number'
          ? payload.size_bytes
          : typeof meta.size === 'number'
            ? meta.size
            : typeof meta.size_bytes === 'number'
              ? meta.size_bytes
              : file?.size,
    mime:
      (typeof payload.mime === 'string' && payload.mime) ||
      (typeof payload.mime_type === 'string' && payload.mime_type) ||
      (typeof meta.mime === 'string' && meta.mime) ||
      file?.type ||
      null,
    rn:
      (typeof payload.rn === 'string' && payload.rn) ||
      (typeof meta.rn === 'string' && meta.rn) ||
      null,
    hostedUri:
      (typeof payload.hosted_uri === 'string' && payload.hosted_uri) ||
      (typeof payload.path === 'string' && payload.path) ||
      (typeof payload.source_path === 'string' && payload.source_path) ||
      null,
    description:
      (typeof payload.summary === 'string' && payload.summary) ||
      (typeof payload.description === 'string' && payload.description) ||
      null,
    file,
  }
}

function createEmptyTurn(turnId: string, createdAt: number, message = ''): ChatTurn {
  return {
    id: turnId,
    state: 'completed',
    createdAt,
    userMessage: message,
    userAttachments: [],
    additionalUserMessages: [],
    answer: '',
    error: null,
    steps: {},
    artifacts: [],
    timeline: [],
    followups: [],
  }
}

function hydrateHistoricalConversation(conversation: ConversationDTO): ChatTurn[] {
  return (conversation.turns || []).map((turnDto, turnIndex) => {
    let turn = createEmptyTurn(turnDto.turn_id, Date.now())

    for (const artifact of turnDto.artifacts || []) {
      const ts = timestampValue(artifact.ts)
      const payload = extractPayload(artifact.data)

      switch (artifact.type) {
        case 'chat:user': {
          const dataRecord = artifact.data && typeof artifact.data === 'object'
            ? artifact.data as Record<string, unknown>
            : {}
          const text =
            (typeof artifact.data?.text === 'string' && artifact.data.text) ||
            (typeof payload.text === 'string' && payload.text) ||
            ''
          const continuationKind =
            (typeof dataRecord.continuation_kind === 'string' && dataRecord.continuation_kind) ||
            (typeof payload.continuation_kind === 'string' && payload.continuation_kind) ||
            null
          if (turn.userMessage || continuationKind === 'followup' || continuationKind === 'steer') {
            turn = {
              ...turn,
              createdAt: Math.min(turn.createdAt, ts),
              additionalUserMessages: [
                ...turn.additionalUserMessages,
                {
                  id: `stored-user:${turnDto.turn_id}:${turn.additionalUserMessages.length}`,
                  text,
                  timestamp: ts,
                  attachments: [],
                  continuationKind: continuationKind === 'steer' ? 'steer' : 'followup',
                },
              ],
            }
            break
          }
          turn = {
            ...turn,
            createdAt: ts,
            userMessage: text,
          }
          break
        }
        case 'artifact:user.attachment': {
          turn = {
            ...turn,
            createdAt: Math.min(turn.createdAt, ts),
            userAttachments: [
              ...turn.userAttachments,
              normalizeTurnAttachment(payload, `stored:${turnDto.turn_id}:${turn.userAttachments.length}`),
            ],
          }
          break
        }
        case 'chat:assistant': {
          const text =
            (typeof artifact.data?.text === 'string' && artifact.data.text) ||
            (typeof payload.text === 'string' && payload.text) ||
            ''
          turn = {
            ...turn,
            answer: text,
            timeline: [
              ...turn.timeline,
              {
                id: `history:answer:${turnDto.turn_id}`,
                timestamp: ts,
                kind: 'answer',
                title: 'Assistant answer',
                body: text,
                format: 'markdown',
                status: 'completed',
              },
            ],
          }
          break
        }
        case 'artifact:assistant.file': {
          const normalized = normalizeTurnAttachment(payload, `assistant-file:${turnDto.turn_id}:${turn.artifacts.length}`)
          const fileArtifact: FileArtifact = {
            kind: 'file',
            timestamp: ts,
            filename: normalized.name,
            rn: normalized.rn || normalized.hostedUri || normalized.id,
            mime: normalized.mime,
            description: normalized.description,
          }
          turn = {
            ...turn,
            artifacts: upsertArtifact(
              turn.artifacts,
              (item) => item.kind === 'file' && item.rn === fileArtifact.rn,
              fileArtifact,
            ),
          }
          break
        }
        case 'artifact:conv.user_shortcuts': {
          const items = Array.isArray(payload.items)
            ? payload.items.filter((item): item is string => typeof item === 'string')
            : []
          turn = {
            ...turn,
            followups: items,
          }
          break
        }
        case 'artifact:solver.program.citables': {
          const items = Array.isArray(payload.items) ? payload.items : []
          let artifacts = turn.artifacts.slice()
          for (const item of items) {
            if (!item || typeof item !== 'object') continue
            const row = item as Record<string, unknown>
            const url = typeof row.url === 'string' ? row.url : ''
            if (!url) continue
            artifacts = upsertArtifact(artifacts, (artifactItem) => artifactItem.kind === 'citation' && artifactItem.url === url, {
              kind: 'citation',
              timestamp: ts,
              url,
              title: typeof row.title === 'string' ? row.title : null,
              body: typeof row.text === 'string' ? row.text : null,
              favicon: typeof row.favicon === 'string' ? row.favicon : null,
            })
          }
          turn = {
            ...turn,
            artifacts,
          }
          break
        }
        case 'artifact:conv.timeline_text.stream': {
          const items = Array.isArray(payload.items) ? payload.items : []
          let artifacts = turn.artifacts.slice()
          let timeline = turn.timeline.slice()
          for (const item of items) {
            if (!item || typeof item !== 'object') continue
            const row = item as Record<string, unknown>
            const name = typeof row.artifact_name === 'string' ? row.artifact_name : 'timeline'
            const text = typeof row.text === 'string' ? row.text : ''
            const itemTs = typeof row.ts_first === 'number' ? row.ts_first : ts
            const nextArtifact: TimelineArtifact = {
              kind: 'timeline',
              timestamp: itemTs,
              name,
              markdown: text,
            }
            artifacts = upsertArtifact(artifacts, (artifactItem) => artifactItem.kind === 'timeline' && artifactItem.name === name, nextArtifact)
            timeline = upsertTimelineEntry(timeline, (entry) => entry.id === `timeline:${name}`, {
              id: `timeline:${name}`,
              timestamp: itemTs,
              kind: 'timeline',
              title: name,
              body: text,
              format: 'markdown',
              status: 'completed',
            })
          }
          turn = {
            ...turn,
            artifacts,
            timeline,
          }
          break
        }
        case 'artifact:conv.thinking.stream': {
          const items = Array.isArray(payload.items) ? payload.items : []
          let timeline = turn.timeline.slice()
          for (const item of items) {
            if (!item || typeof item !== 'object') continue
            const row = item as Record<string, unknown>
            const agent = typeof row.agent === 'string' ? row.agent : 'assistant'
            const text = typeof row.text === 'string' ? row.text : ''
            const itemTs = typeof row.ts_first === 'number' ? row.ts_first : ts
            timeline = upsertTimelineEntry(timeline, (entry) => entry.id === `thinking:${agent}`, {
              id: `thinking:${agent}`,
              timestamp: itemTs,
              kind: 'thinking',
              title: `Reasoning • ${agent}`,
              body: text,
              format: 'markdown',
              agent,
              status: 'completed',
            })
          }
          turn = {
            ...turn,
            timeline,
          }
          break
        }
        case 'artifact:conv.artifacts.stream': {
          const items = Array.isArray(payload.items) ? payload.items : []
          let tempState: ChatState = {
            ...initialState,
            conversationId: conversation.conversation_id,
            conversationTitle: conversation.conversation_title || null,
            turns: [{ ...turn }],
          }
          items.forEach((item, index) => {
            if (!item || typeof item !== 'object') return
            const row = item as Record<string, unknown>
            const syntheticEnv: ChatDeltaEnvelope = {
              type: 'chat.delta',
              timestamp: typeof row.ts_first === 'number' ? new Date(row.ts_first).toISOString() : (artifact.ts || new Date(ts).toISOString()),
              service: { request_id: `history:${conversation.conversation_id}:${turnDto.turn_id}` },
              conversation: {
                session_id: '',
                conversation_id: conversation.conversation_id,
                turn_id: turnDto.turn_id,
              },
              event: {
                step: 'historical',
                status: 'completed',
                title: typeof row.title === 'string' ? row.title : null,
                agent: typeof row.agent === 'string' ? row.agent : null,
              },
              data: {},
              delta: {
                text: typeof row.text === 'string' ? row.text : '',
                marker: typeof row.marker === 'string' ? row.marker : 'subsystem',
                index,
                completed: true,
              },
              extra: {
                ...(row.extra && typeof row.extra === 'object' ? (row.extra as Record<string, unknown>) : {}),
                artifact_name: typeof row.artifact_name === 'string' ? row.artifact_name : undefined,
                title: typeof row.title === 'string' ? row.title : undefined,
                format: typeof row.format === 'string' ? row.format : undefined,
              },
            }
            tempState = applyChatDelta(tempState, syntheticEnv)
          })
          turn = tempState.turns[0] || turn
          break
        }
        default:
          break
      }
    }

    const sortedTimeline = turn.timeline.slice().sort((left, right) => left.timestamp - right.timestamp)
    const hydratedTurn: ChatTurn = {
      ...turn,
      createdAt: Number.isFinite(turn.createdAt) ? turn.createdAt : Date.now() + turnIndex,
      state: 'completed',
      timeline: sortedTimeline,
    }
    return hydratedTurn
  }).sort((left, right) => left.createdAt - right.createdAt)
}

function applyChatStart(state: ChatState, env: ChatStartEnvelope): ChatState {
  const timestamp = timestampValue(env.timestamp)
  const ensuredState = ensureTurn(
    state,
    env.conversation.turn_id,
    timestamp,
    typeof env.data?.message === 'string' ? env.data.message : '',
  )
  const syncedState = syncConversationFromEnvelope(ensuredState, env)
  return updateTurn(syncedState, env.conversation.turn_id, (turn) => ({
    ...turn,
    state: 'running',
    timeline: [
      ...turn.timeline,
      {
        id: `lifecycle:start:${env.service.request_id}:${env.conversation.turn_id}`,
        timestamp,
        kind: 'lifecycle',
        title: 'Turn started',
        body: typeof env.data?.message === 'string' ? env.data.message : undefined,
        format: 'text',
        status: 'started',
        agent: env.event.agent,
      },
    ],
  }))
}

function applyChatComplete(state: ChatState, env: ChatCompleteEnvelope): ChatState {
  const ensuredState = ensureTurn(state, env.conversation.turn_id, timestampValue(env.timestamp))
  const syncedState = syncConversationFromEnvelope(ensuredState, env)
  return updateTurn(syncedState, env.conversation.turn_id, (turn) => {
    const completeFollowups = Array.isArray(env.data?.followups)
      ? (env.data.followups as unknown[]).filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : []
    return {
      ...turn,
      state: env.data?.error_message ? 'error' : 'completed',
      // The visible answer comes from streamed `marker="answer"` deltas, where citation tokens
      // [[S:n]] are replaced into resolved links live. The chat.complete envelope may still
      // carry `data.final_answer` in raw token form; reading it here would arrive after the
      // stream completes and clobber the rendered text. Keep `turn.answer` (streamed text).
      answer: turn.answer,
      error: (env.data?.error_message as string | undefined) || turn.error,
      // `chat.followups` usually arrives as a completed step before `chat.complete`.
      // Some completion envelopes still carry an empty followups array, so only use
      // completion followups when they are actually populated.
      followups: completeFollowups.length ? completeFollowups : turn.followups,
      timeline: [
        ...turn.timeline,
        {
          id: `lifecycle:complete:${env.service.request_id}:${env.conversation.turn_id}`,
          timestamp: timestampValue(env.timestamp),
          kind: 'lifecycle',
          title: env.data?.error_message ? 'Turn completed with error' : 'Turn completed',
          body: typeof env.data?.selected_model === 'string' ? `Model: ${env.data.selected_model}` : undefined,
          format: 'text',
          status: env.data?.error_message ? 'error' : 'completed',
          agent: env.event.agent,
        },
      ],
    }
  })
}

function applyChatError(state: ChatState, env: ChatErrorEnvelope): ChatState {
  const message = env.data?.error || 'Request failed.'
  const ensuredState = ensureTurn(state, env.conversation.turn_id, timestampValue(env.timestamp))
  const syncedState = syncConversationFromEnvelope(ensuredState, env)
  return updateTurn(syncedState, env.conversation.turn_id, (turn) => ({
    ...turn,
    state: 'error',
    error: message,
    artifacts: [
      ...turn.artifacts,
      {
        kind: 'service_error',
        timestamp: timestampValue(env.timestamp),
        message,
      },
    ],
    timeline: [
      ...turn.timeline,
      {
        id: `error:${env.service.request_id}:${env.conversation.turn_id}:${turn.timeline.length}`,
        timestamp: timestampValue(env.timestamp),
        kind: 'error',
        title: 'Error',
        body: message,
        format: 'text',
        status: 'error',
        agent: env.event.agent,
      },
    ],
  }))
}

function applyConvStatus(state: ChatState, env: ConvStatusEnvelope): ChatState {
  if (!state.conversationId || env.conversation.conversation_id !== state.conversationId) {
    return state
  }
  if (env.data.state === 'in_progress') return state
  const turns = state.turns.map((turn) => {
    if (turn.state === 'pending' || turn.state === 'running') {
      const nextState: TurnState = env.data.state === 'error' ? 'error' : 'completed'
      return {
        ...turn,
        state: nextState,
        error:
          env.data.state === 'error' && turn.error == null
            ? 'Conversation ended with an error.'
            : turn.error,
      }
    }
    return turn
  })
  return { ...state, turns }
}

function applyChatStep(state: ChatState, env: ChatStepEnvelope): ChatState {
  const syncedState = syncConversationFromEnvelope(
    ensureTurn(state, env.conversation.turn_id, timestampValue(env.timestamp)),
    env,
  )
  return updateTurn(syncedState, env.conversation.turn_id, (turn) => {
    const timestamp = timestampValue(env.timestamp)
    const nextStep: TurnStep = {
      step: env.event.step,
      title: env.event.title,
      status: env.event.status,
      timestamp: turn.steps[env.event.step]?.timestamp ?? timestamp,
      error: typeof env.data?.error === 'string' ? env.data.error : undefined,
      markdown: env.event.markdown,
      agent: env.event.agent,
      data: env.data,
    }

    let artifacts = turn.artifacts.slice()

    if (env.event.status === 'completed') {
      if (env.event.step === 'citations' && Array.isArray(env.data?.items)) {
        for (const item of env.data.items as Array<Record<string, unknown>>) {
          const url = typeof item.url === 'string' ? item.url : ''
          if (!url) continue
          artifacts = upsertArtifact(artifacts, (artifact) => artifact.kind === 'citation' && artifact.url === url, {
            kind: 'citation',
            timestamp,
            url,
            title: typeof item.title === 'string' ? item.title : null,
            body: typeof item.body === 'string' ? item.body : null,
            favicon: typeof item.favicon === 'string' ? item.favicon : null,
          })
        }
      }

      if (env.event.step === 'files' && Array.isArray(env.data?.items)) {
        for (const item of env.data.items as Array<Record<string, unknown>>) {
          const rn = typeof item.rn === 'string' ? item.rn : ''
          const filename = typeof item.filename === 'string' ? item.filename : ''
          if (!rn || !filename) continue
          artifacts = upsertArtifact(artifacts, (artifact) => artifact.kind === 'file' && artifact.rn === rn, {
            kind: 'file',
            timestamp,
            rn,
            filename,
            mime: typeof item.mime === 'string' ? item.mime : null,
            description: typeof item.description === 'string' ? item.description : null,
          })
        }
      }

      if (env.event.step === 'followups' && Array.isArray(env.data?.items)) {
        // chat.followups arrives via the `chat.step` route (status === "completed"),
        // so this is the canonical place to populate turn.followups during a live
        // stream. The reload path populates them directly from the stored
        // `artifact:conv.user_shortcuts`.
        const followups = (env.data.items as unknown[]).filter(
          (item): item is string => typeof item === 'string' && item.trim().length > 0,
        )
        return {
          ...turn,
          steps: {
            ...turn.steps,
            [env.event.step]: nextStep,
          },
          artifacts,
          followups: followups.length ? followups : turn.followups,
        }
      }
    }

    return {
      ...turn,
      steps: {
        ...turn.steps,
        [env.event.step]: nextStep,
      },
      artifacts,
    }
  })
}

function applyChatDelta(state: ChatState, env: ChatDeltaEnvelope): ChatState {
  const turnId = env.conversation.turn_id
  const timestamp = timestampValue(env.timestamp)
  const marker = env.delta?.marker || 'answer'
  const textDelta = env.delta?.text || ''
  const index = env.delta?.index || 0

  const syncedState = syncConversationFromEnvelope(ensureTurn(state, turnId, timestamp), env)
  return updateTurn(syncedState, turnId, (turn) => {
    let nextTurn: ChatTurn = { ...turn }
    let artifacts = turn.artifacts.slice()
    let timeline = turn.timeline.slice()

    switch (marker) {
      case 'answer':
        nextTurn.answer = `${turn.answer}${textDelta}`
        nextTurn.state = 'running'
        timeline = upsertTimelineEntry(timeline, (entry) => entry.id === 'answer:assistant', {
          id: 'answer:assistant',
          timestamp: timeline.find((entry) => entry.id === 'answer:assistant')?.timestamp ?? timestamp,
          kind: 'answer',
          title: timelineTitleForMarker(marker),
          body: `${timeline.find((entry) => entry.id === 'answer:assistant')?.body || ''}${textDelta}`,
          format: 'markdown',
          agent: env.event.agent,
          status: env.event.status,
        })
        break
      case 'thinking': {
        const entryId = `thinking:${env.event.agent || 'assistant'}`
        const current = timeline.find((entry) => entry.id === entryId)
        timeline = upsertTimelineEntry(timeline, (entry) => entry.id === entryId, {
          id: entryId,
          timestamp: current?.timestamp ?? timestamp,
          kind: 'thinking',
          title: timelineTitleForMarker(marker, env.event.agent ? `Reasoning • ${env.event.agent}` : undefined),
          body: `${current?.body || ''}${textDelta}`,
          format: 'markdown',
          agent: env.event.agent,
          status: env.event.status,
        })
        break
      }
      case 'timeline_text': {
        const name = String(env.extra?.artifact_name || 'timeline')
        const current =
          index === 0
            ? null
            : (artifacts.find(
                (artifact) => artifact.kind === 'timeline' && artifact.name === name,
              ) as TimelineArtifact | undefined)
        const nextArtifact: TimelineArtifact = {
          kind: 'timeline',
          timestamp: current?.timestamp ?? timestamp,
          name,
          markdown: `${current?.markdown || ''}${textDelta}`,
        }
        artifacts = upsertArtifact(
          artifacts.filter((artifact) => !(index === 0 && artifact.kind === 'timeline' && artifact.name === name)),
          (artifact) => artifact.kind === 'timeline' && artifact.name === name,
          nextArtifact,
        )
        timeline = upsertTimelineEntry(
          timeline.filter((entry) => !(index === 0 && entry.id === `timeline:${name}`)),
          (entry) => entry.id === `timeline:${name}`,
          {
            id: `timeline:${name}`,
            timestamp: current?.timestamp ?? timestamp,
            kind: 'timeline',
            title: timelineTitleForMarker(marker, name),
            body: nextArtifact.markdown,
            format: 'markdown',
            agent: env.event.agent,
            status: env.event.status,
          },
        )
        break
      }
      case 'canvas': {
        const name = String(env.extra?.artifact_name || 'canvas')
        const format = typeof env.extra?.format === 'string' ? env.extra.format : null
        const title = typeof env.extra?.title === 'string' ? env.extra.title : null
        const current =
          index === 0
            ? null
            : (artifacts.find(
                (artifact) => artifact.kind === 'canvas' && artifact.name === name,
              ) as CanvasArtifact | undefined)
        const nextArtifact: CanvasArtifact = {
          kind: 'canvas',
          timestamp: current?.timestamp ?? timestamp,
          name,
          title,
          format,
          content: `${current?.content || ''}${textDelta}`,
        }
        artifacts = upsertArtifact(
          artifacts.filter((artifact) => !(index === 0 && artifact.kind === 'canvas' && artifact.name === name)),
          (artifact) => artifact.kind === 'canvas' && artifact.name === name,
          nextArtifact,
        )
        timeline = upsertTimelineEntry(
          timeline.filter((entry) => !(index === 0 && entry.id === `canvas:${name}`)),
          (entry) => entry.id === `canvas:${name}`,
          {
            id: `canvas:${name}`,
            timestamp: current?.timestamp ?? timestamp,
            kind: 'canvas',
            title: timelineTitleForMarker(marker, title || name),
            body: nextArtifact.content,
            format: format === 'markdown' ? 'markdown' : 'text',
            agent: env.event.agent,
            status: env.event.status,
          },
        )
        break
      }
      case 'subsystem': {
        const subtype = String(env.extra?.sub_type || '')
        const artifactName = String(env.extra?.artifact_name || 'Subsystem')
        const title = typeof env.extra?.title === 'string' ? env.extra.title : null
        const timelineEntryId = `subsystem:${subtype}:${String(env.extra?.execution_id || env.extra?.search_id || artifactName)}`
        let timelineBody = textDelta
        let timelineFormat: TimelineEntryFormat = 'text'
        if (subtype === 'web_search.filtered_results' || subtype === 'web_search.html_view') {
          const searchId = String(env.extra?.search_id || artifactName)
          const current = artifacts.find(
            (artifact) => artifact.kind === 'web_search' && artifact.searchId === searchId,
          ) as WebSearchArtifact | undefined
          const base: WebSearchArtifact = current || {
            kind: 'web_search',
            timestamp,
            searchId,
            name: artifactName,
            title,
            queries: [],
            items: [],
            objective: undefined,
            reportContent: null,
          }
          let nextArtifact = { ...base, title: title || base.title, name: artifactName || base.name }
          if (subtype === 'web_search.filtered_results') {
            const parsed = safeJsonParse<Record<string, unknown>>(textDelta, {})
            nextArtifact = {
              ...nextArtifact,
              objective: typeof parsed.objective === 'string' ? parsed.objective : nextArtifact.objective,
              queries: Array.isArray(parsed.queries)
                ? parsed.queries.filter((item): item is string => typeof item === 'string')
                : nextArtifact.queries,
              items: Array.isArray(parsed.results)
                ? (parsed.results as WebSearchItem[])
                : nextArtifact.items,
            }
            timelineBody = prettyJson(parsed)
            timelineFormat = 'json'
          } else {
            nextArtifact = {
              ...nextArtifact,
              reportContent: `${nextArtifact.reportContent || ''}${textDelta}`,
            }
            timelineBody = nextArtifact.reportContent || textDelta
            timelineFormat = 'markdown'
          }
          artifacts = upsertArtifact(artifacts, (artifact) => artifact.kind === 'web_search' && artifact.searchId === searchId, nextArtifact)
        } else if (subtype === 'web_fetch.results') {
          const executionId = String(env.extra?.execution_id || artifactName)
          const parsed = safeJsonParse<Record<string, unknown>>(textDelta, {})
          const nextArtifact: WebFetchArtifact = {
            kind: 'web_fetch',
            timestamp,
            executionId,
            name: artifactName,
            title,
            items: Array.isArray(parsed.urls) ? (parsed.urls as WebFetchItem[]) : [],
          }
          artifacts = upsertArtifact(artifacts, (artifact) => artifact.kind === 'web_fetch' && artifact.executionId === executionId, nextArtifact)
          timelineBody = prettyJson(parsed)
          timelineFormat = 'json'
        } else if (subtype.startsWith('code_exec.')) {
          const executionId = String(env.extra?.execution_id || artifactName)
          const current = artifacts.find(
            (artifact) => artifact.kind === 'code_exec' && artifact.executionId === executionId,
          ) as CodeExecArtifact | undefined
          const base: CodeExecArtifact = current || {
            kind: 'code_exec',
            timestamp,
            executionId,
            title,
          }
          let nextArtifact: CodeExecArtifact = {
            ...base,
            name: artifactName || base.name,
            title: title || base.title,
          }
          if (subtype === 'code_exec.code') {
            nextArtifact = {
              ...nextArtifact,
              language: typeof env.extra?.language === 'string' ? env.extra.language : nextArtifact.language,
              program: `${index === 0 ? '' : nextArtifact.program || ''}${textDelta}`,
            }
            timelineBody = nextArtifact.program || textDelta
            timelineFormat = 'code'
          } else if (subtype === 'code_exec.program.name') {
            nextArtifact = { ...nextArtifact, name: textDelta || nextArtifact.name }
            timelineBody = nextArtifact.name || textDelta
          } else if (subtype === 'code_exec.objective') {
            nextArtifact = { ...nextArtifact, objective: textDelta || nextArtifact.objective }
            timelineBody = nextArtifact.objective || textDelta
          } else if (subtype === 'code_exec.contract') {
            const parsed = safeJsonParse<Record<string, unknown>>(textDelta, {})
            nextArtifact = {
              ...nextArtifact,
              contract: Array.isArray(parsed.contract) ? (parsed.contract as CodeExecContractItem[]) : nextArtifact.contract,
            }
            timelineBody = prettyJson(parsed)
            timelineFormat = 'json'
          } else if (subtype === 'code_exec.status') {
            const parsed = safeJsonParse<Record<string, unknown>>(textDelta, {})
            nextArtifact = {
              ...nextArtifact,
              status: (parsed.status as CodeExecStatus | undefined) || nextArtifact.status,
            }
            timelineBody = prettyJson(parsed)
            timelineFormat = 'json'
          }
          artifacts = upsertArtifact(artifacts, (artifact) => artifact.kind === 'code_exec' && artifact.executionId === executionId, nextArtifact)
        }
        timeline = upsertTimelineEntry(
          timeline.filter((entry) => !(index === 0 && entry.id === timelineEntryId)),
          (entry) => entry.id === timelineEntryId,
          {
            id: timelineEntryId,
            timestamp: timeline.find((entry) => entry.id === timelineEntryId)?.timestamp ?? timestamp,
            kind: 'subsystem',
            title: timelineTitleForSubsystem(subtype, title || artifactName),
            body: timelineFormat === 'markdown'
              ? `${index === 0 ? '' : timeline.find((entry) => entry.id === timelineEntryId)?.body || ''}${timelineBody}`
              : timelineBody,
            format: timelineFormat,
            agent: env.event.agent,
            status: env.event.status,
          },
        )
        break
      }
      default:
        timeline = upsertTimelineEntry(timeline, (entry) => entry.id === `delta:${marker}`, {
          id: `delta:${marker}`,
          timestamp: timeline.find((entry) => entry.id === `delta:${marker}`)?.timestamp ?? timestamp,
          kind: 'timeline',
          title: timelineTitleForMarker(marker, marker),
          body: `${timeline.find((entry) => entry.id === `delta:${marker}`)?.body || ''}${textDelta}`,
          format: 'text',
          agent: env.event.agent,
          status: env.event.status,
        })
        break
    }

    // followups handling moved to applyChatStep (chat.followups is dispatched as
    // a `chat.step` event with step === "followups", not a delta).

    return {
      ...nextTurn,
      artifacts,
      timeline,
    }
  })
}

/* MarkdownBlock is now imported from ./components/MarkdownBlock.tsx */






/* Highlight tokens, CopyButton, DownloadButton, Snippet, canvas helpers and CanvasRender extracted to ./components/* */



/* CaretIcon is now imported from ./components/CaretIcon.tsx */








export default function App() {
  const [state, setState] = useState<ChatState>(initialState)
  const [ready, setReady] = useState(false)
  const [bootError, setBootError] = useState<string | null>(null)
  const [conversationQuery, setConversationQuery] = useState('')

  const stateRef = useRef(state)
  const eventSourceRef = useRef<EventSource | null>(null)
  const connectPromiseRef = useRef<Promise<void> | null>(null)
  const sessionIdRef = useRef<string | null>(null)
  const streamIdRef = useRef<string | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const autoScrollRef = useRef(true)
  const [showScrollDown, setShowScrollDown] = useState(false)

  useEffect(() => {
    stateRef.current = state
  }, [state])

  useEffect(() => {
    const updateAutoScroll = () => {
      const doc = document.documentElement
      const scrollTop = window.scrollY || doc.scrollTop || 0
      const remaining = doc.scrollHeight - (scrollTop + window.innerHeight)
      const near = remaining < 140
      autoScrollRef.current = near
      setShowScrollDown(!near && doc.scrollHeight > window.innerHeight + 80)
    }

    updateAutoScroll()
    window.addEventListener('scroll', updateAutoScroll, { passive: true })
    window.addEventListener('resize', updateAutoScroll)
    return () => {
      window.removeEventListener('scroll', updateAutoScroll)
      window.removeEventListener('resize', updateAutoScroll)
    }
  }, [])

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }

  useEffect(() => {
    if (!autoScrollRef.current) return
    bottomRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' })
  }, [state.turns, state.banners, ready])

  const hasPendingTurn = state.turns.some((turn) => turn.state === 'pending' || turn.state === 'running')
  const bundleId = settings.getBundleId() || BUILT_BUNDLE_ID
  const filteredConversations = useMemo(() => {
    const query = conversationQuery.trim().toLowerCase()
    const items = state.conversations.slice().sort((left, right) => (right.lastActivityAt || 0) - (left.lastActivityAt || 0))
    if (!query) return items
    return items.filter((item) => {
      const haystack = `${item.title || ''} ${item.id}`.toLowerCase()
      return haystack.includes(query)
    })
  }, [conversationQuery, state.conversations])

  const refreshConversationList = async () => {
    if (!bundleId) return

    setState((previous) => ({
      ...previous,
      conversationsLoading: true,
      conversationsError: null,
    }))

    try {
      const conversations = await listBundleConversations(bundleId)
      setState((previous) => ({
        ...previous,
        conversations,
        conversationsLoading: false,
        conversationsError: null,
      }))
    } catch (error) {
      const message = messageForError(error)
      setState((previous) => ({
        ...previous,
        conversationsLoading: false,
        conversationsError: message,
      }))
    }
  }

  const requestConversationStatusForCurrentStream = async (conversationId: string) => {
    const streamId = streamIdRef.current
    if (!streamId) return
    try {
      await requestConversationStatus(conversationId, streamId)
    } catch (error) {
      console.warn('Unable to request conversation status', error)
    }
  }

  const loadConversation = async (conversationId: string) => {
    setState((previous) => ({
      ...previous,
      conversationLoadingId: conversationId,
      inputLocked: false,
      inputLockMessage: null,
    }))

    try {
      const conversation = await fetchConversationById(conversationId)
      const turns = hydrateHistoricalConversation(conversation)

      setState((previous) => ({
        ...previous,
        conversationId: conversation.conversation_id,
        conversationTitle: conversation.conversation_title || null,
        turns,
        composerText: '',
        composerFiles: [],
        conversationLoadingId: null,
      }))

      if (stateRef.current.connection === 'connected') {
        void requestConversationStatusForCurrentStream(conversation.conversation_id)
      }
    } catch (error) {
      const message = messageForError(error)
      setState((previous) => ({
        ...previous,
        conversationLoadingId: null,
      }))
      setBootError(message)
    }
  }

  const startNewChat = () => {
    setState((previous) => ({
      ...previous,
      conversationId: null,
      conversationTitle: null,
      turns: [],
      composerText: '',
      composerFiles: [],
      inputLocked: false,
      inputLockMessage: null,
      conversationLoadingId: null,
    }))
  }

  const resetTransport = () => {
    eventSourceRef.current?.close()
    eventSourceRef.current = null
    streamIdRef.current = null
    connectPromiseRef.current = null
  }

  const handleServiceEvent = (env: ChatServiceEnvelope) => {
    const data = (env.data || {}) as Record<string, unknown>
    const rateLimit = (env.data?.rate_limit || null) as RateLimitPayload | null

    let tone: BannerTone = (rateLimit?.notification_type || data.notification_type || 'warning') as BannerTone
    let message = ''

    switch (env.type) {
      case 'rate_limit.warning':
      case 'rate_limit.denied':
      case 'rate_limit.post_run_exceeded':
        message = rateLimit?.user_message || fallbackRateLimitMessage(rateLimit || undefined, data)
        break
      case 'rate_limit.no_funding':
        tone = (data.notification_type as BannerTone | undefined) || 'error'
        message = (data.user_message as string | undefined) || 'This service is not available for your account type.'
        break
      case 'rate_limit.subscription_exhausted':
        tone = (data.notification_type as BannerTone | undefined) || 'error'
        message =
          (data.user_message as string | undefined) ||
          'Your subscription balance is exhausted. Top up your balance to continue.'
        break
      case 'rate_limit.project_exhausted': {
        tone = 'error'
        const hasPersonalBudget = Boolean(data.has_personal_budget)
        const usdShort = typeof data.usd_short === 'number' ? data.usd_short : null
        if (hasPersonalBudget && usdShort && usdShort > 0) {
          message = `Project budget exhausted. You need $${usdShort.toFixed(2)} more in personal credits to run this request.`
        } else if (!hasPersonalBudget) {
          message = 'Project budget exhausted. Please contact your administrator to add funds.'
        } else {
          message = 'Project budget exhausted. Unable to process this request.'
        }
        break
      }
      case 'rate_limit.attachment_failure':
        tone = (data.notification_type as BannerTone | undefined) || 'error'
        message = (data.user_message as string | undefined) || 'Attachment was rejected.'
        break
      case 'rate_limit.lane_switch':
      case 'economics.user_underfunded_absorbed':
        return
      default:
        message =
          rateLimit?.user_message ||
          (data.user_message as string | undefined) ||
          `${env.type}: service message received`
    }

    setState((previous) => {
      let next = addBanner(previous, tone, message)
      const shouldLockInput =
        tone === 'error' &&
        env.type !== 'rate_limit.attachment_failure' &&
        env.type !== 'rate_limit.warning'

      if (shouldLockInput) {
        next = {
          ...next,
          inputLocked: true,
          inputLockMessage: message,
        }
      }

      if (env.type === 'rate_limit.attachment_failure') {
        next = {
          ...next,
          composerFiles: [],
        }
      }

      return next
    })
  }

  const connectStream = async () => {
    if (eventSourceRef.current && streamIdRef.current) {
      return
    }

    if (connectPromiseRef.current) {
      await connectPromiseRef.current
      return
    }

    connectPromiseRef.current = (async () => {
      setState((previous) => ({ ...previous, connection: 'connecting' }))
      const transport = await openChatStream({
        sessionId: sessionIdRef.current,
        onChatStart: (env) => {
          setState((previous) => applyChatStart(previous, env))
        },
        onChatStep: (env) => {
          setState((previous) => applyChatStep(previous, env))
        },
        onChatDelta: (env) => {
          setState((previous) => applyChatDelta(previous, env))
        },
        onChatComplete: (env) => {
          setState((previous) => applyChatComplete(previous, env))
          void refreshConversationList()
        },
        onChatError: (env) => {
          setState((previous) => applyChatError(previous, env))
        },
        onConversationStatus: (env) => {
          setState((previous) => applyConvStatus(previous, env))
        },
        onChatService: handleServiceEvent,
        onDisconnect: () => {
          setState((previous) => ({ ...previous, connection: 'disconnected' }))
        },
      })

      eventSourceRef.current = transport.eventSource
      streamIdRef.current = transport.streamId
      sessionIdRef.current = transport.sessionId
      setState((previous) => ({
        ...previous,
        connection: 'connected',
        sessionId: transport.sessionId,
      }))
      if (stateRef.current.conversationId) {
        void requestConversationStatusForCurrentStream(stateRef.current.conversationId)
      }
    })()

    try {
      await connectPromiseRef.current
    } catch (error) {
      resetTransport()
      setState((previous) => ({ ...previous, connection: 'disconnected' }))
      throw error
    } finally {
      connectPromiseRef.current = null
    }
  }

  const sendMessage = async (textOverride?: string, requestedKind?: ContinuationKind) => {
    const snapshot = stateRef.current
    const activeTurn = findActiveTurn(snapshot.turns)
    let continuationKind: ContinuationKind = requestedKind ?? (activeTurn ? 'followup' : 'regular')
    if (continuationKind !== 'regular' && !activeTurn) {
      continuationKind = 'regular'
    }
    const isContinuation = continuationKind === 'followup' || continuationKind === 'steer'
    const isSteer = continuationKind === 'steer'
    const continuationMessageKind: Exclude<ContinuationKind, 'regular'> =
      continuationKind === 'steer' ? 'steer' : 'followup'
    const targetTurnId = isContinuation ? activeTurn?.id : undefined
    const draftText = (textOverride ?? snapshot.composerText).trim()
    const draftFiles = isSteer || textOverride !== undefined ? [] : snapshot.composerFiles
    if (!draftText && draftFiles.length === 0 && !isSteer) return

    const sentAt = Date.now()
    const existingConversationId = snapshot.conversationId
    setState((previous) => ({
      ...previous,
      composerText: '',
      composerFiles: [],
    }))

    try {
      await connectStream()
      const streamId = streamIdRef.current
      if (!streamId) {
        throw new Error('No SSE stream is available.')
      }
      const response = await submitChatMessage({
        streamId,
        bundleId,
        conversationId: existingConversationId,
        text: draftText,
        files: draftFiles,
        chatHistory: isContinuation ? [] : buildChatHistory(snapshot.turns),
        ...(isContinuation
          ? {
              messageKind: continuationKind,
              continuationKind,
              activeTurnId: targetTurnId,
              targetTurnId,
              followup: continuationKind === 'followup',
              steer: continuationKind === 'steer',
            }
          : {}),
      })
      if (!response.turnId) {
        throw new Error('sse/chat response did not include a turn_id')
      }
      const turnId = response.turnId
      const draftAttachments = draftFiles.map((file, index) =>
        normalizeTurnAttachment(
          {
            filename: file.name,
            size: file.size,
            mime: file.type,
          },
          `live:${turnId}:${index}`,
          file,
        ),
      )
      setState((previous) => {
        const stillOwnsTurn = isContinuation
          ? previous.turns.some((turn) => turn.id === targetTurnId)
          : true
        const canBindConversation =
          !previous.conversationId ||
          previous.conversationId === existingConversationId ||
          previous.conversationId === response.conversationId
        if (!stillOwnsTurn || !canBindConversation) return previous
        let next: ChatState = {
          ...previous,
          conversationId: response.conversationId,
        }
        const ackStatus = typeof response.status === 'string' ? response.status : null
        const serverTurnId = response.turnId || turnId
        const continuationAccepted = ackStatus === 'followup_accepted' || ackStatus === 'steer_accepted'
        const continuationStartedNewTurn = isContinuation && !!ackStatus && !continuationAccepted
        const liveContinuationAccepted = continuationAccepted && response.liveOwnerDetected !== false
        const visualContinuationTurnId = response.activeTurnId || targetTurnId
        const continuationMessageId = response.eventId || response.queuedTurnId || serverTurnId
        if (isContinuation && visualContinuationTurnId && liveContinuationAccepted && !isSteer) {
          next = {
            ...next,
            turns: next.turns.map((turn) => {
              if (turn.id !== visualContinuationTurnId) return turn
              if (turn.additionalUserMessages.some((message) => message.id === `continuation:${continuationMessageId}`)) return turn
              return {
                ...turn,
                additionalUserMessages: [
                  ...turn.additionalUserMessages,
                  {
                    id: `continuation:${continuationMessageId}`,
                    text: draftText,
                    timestamp: sentAt,
                    attachments: draftAttachments,
                    continuationKind: continuationMessageKind,
                  },
                ],
              }
            }),
          }
        }
        if (continuationStartedNewTurn && !next.turns.some((turn) => turn.id === serverTurnId)) {
          next = {
            ...next,
            turns: [
              ...next.turns,
              {
                id: serverTurnId,
                state: 'pending',
                createdAt: sentAt,
                userMessage: draftText,
                userAttachments: draftAttachments,
                additionalUserMessages: [],
                answer: '',
                error: null,
                steps: {},
                artifacts: [],
                timeline: [],
                followups: [],
              },
            ],
          }
        } else if (!isContinuation) {
          const existingIndex = next.turns.findIndex((turn) => turn.id === serverTurnId)
          if (existingIndex >= 0) {
            const turns = [...next.turns]
            turns[existingIndex] = {
              ...turns[existingIndex],
              state: turns[existingIndex].state === 'idle' ? 'pending' : turns[existingIndex].state,
              userMessage: turns[existingIndex].userMessage || draftText,
              userAttachments: turns[existingIndex].userAttachments.length
                ? turns[existingIndex].userAttachments
                : draftAttachments,
            }
            next = { ...next, turns }
          } else {
            next = {
              ...next,
              turns: [
                ...next.turns,
                {
                  id: serverTurnId,
                  state: 'pending',
                  createdAt: sentAt,
                  userMessage: draftText,
                  userAttachments: draftAttachments,
                  additionalUserMessages: [],
                  answer: '',
                  error: null,
                  steps: {},
                  artifacts: [],
                  timeline: [],
                  followups: [],
                },
              ],
            }
          }
        }
        return next
      })
      void refreshConversationList()
    } catch (error) {
      const text = messageForError(error)
      const errorTurnId = isContinuation && targetTurnId ? targetTurnId : createLocalId('client_submit_error')
      setState((previous) => applyChatError(previous, {
        type: 'chat.error',
        timestamp: new Date().toISOString(),
        service: { request_id: createLocalId('request') },
        conversation: {
          session_id: previous.sessionId || '',
          conversation_id: existingConversationId || previous.conversationId || '',
          turn_id: errorTurnId,
        },
        event: {
          step: 'send',
          status: 'error',
          title: 'Send failed',
        },
        data: { error: text },
      }))
    }
  }

  const handleReconnect = async () => {
    resetTransport()
    try {
      await connectStream()
      setBootError(null)
    } catch (error) {
      setBootError(messageForError(error))
    }
  }

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        await settings.setupParentListener()
        if (!mounted) return
        setReady(true)
        await connectStream()
      } catch (error) {
        if (!mounted) return
        setBootError(messageForError(error))
      }
    })()

    return () => {
      mounted = false
      resetTransport()
    }
  }, [])

  useEffect(() => {
    if (!ready) return
    void refreshConversationList()
  }, [ready, bundleId])

  if (!ready) {
    return (
      <div className="shell-grid flex min-h-screen items-center justify-center px-6">
        <div className="glass-panel px-6 py-5 text-center">
          <div className="k-status k-live justify-center">Connecting application config…</div>
        </div>
      </div>
    )
  }

  const connectionDotClass =
    state.connection === 'connected'
      ? 'k-status'
      : state.connection === 'disconnected'
        ? 'k-status k-crit'
        : 'k-status k-live'

  return (
    <div className="shell-grid">
      <button
        type="button"
        className={`k-scroll-to-bottom ${showScrollDown ? 'k-show' : ''}`}
        onClick={scrollToBottom}
        aria-label="Scroll to latest"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 5v14M5 12l7 7 7-7" />
        </svg>
        <span>Latest</span>
      </button>
      <div className="mx-auto flex min-h-screen w-full max-w-[1320px] flex-col">
        <header className="k-appbar">
          <div className="k-brand min-w-0">
            <span className="k-brand-mark" aria-hidden="true" />
            <span className="k-brand-name">Versatile</span>
            <span className="k-brand-sep">/</span>
            <span className="k-brand-path">{bundleId}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className={connectionDotClass}>
              {state.connection === 'connected'
                ? `${settings.getTenant() || 'tenant'} / ${settings.getProject() || 'project'}`
                : state.connection}
            </span>
            <button
              type="button"
              onClick={handleReconnect}
              className="k-iconbtn"
              aria-label="Reconnect"
              title="Reconnect"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12a9 9 0 1 1-3-6.7" />
                <path d="M21 3v6h-6" />
              </svg>
            </button>
            <button
              type="button"
              onClick={startNewChat}
              disabled={hasPendingTurn}
              className="k-btn"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 5v14M5 12h14" />
              </svg>
              New chat
            </button>
          </div>
        </header>

        <main className="flex-1 px-3 py-3 sm:px-4 sm:py-4 lg:px-6 lg:py-5">
          {bootError || state.banners.length > 0 ? (
            <div className="pb-3">
              <BannerStrip
                banners={bootError ? [{ id: 'boot-error', tone: 'error', text: bootError }, ...state.banners] : state.banners}
                onDismiss={(id) => {
                  if (id === 'boot-error') {
                    setBootError(null)
                    return
                  }
                  setState((previous) => ({
                    ...previous,
                    banners: previous.banners.filter((banner) => banner.id !== id),
                  }))
                }}
              />
            </div>
          ) : null}

          <div className="grid gap-3 lg:gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
            <ConversationsSidebar
              conversations={filteredConversations}
              query={conversationQuery}
              activeConversationId={state.conversationId}
              disabled={hasPendingTurn}
              loading={state.conversationsLoading}
              error={state.conversationsError}
              loadingConversationId={state.conversationLoadingId}
              onQueryChange={setConversationQuery}
              onRefresh={() => void refreshConversationList()}
              onSelect={(conversationId) => void loadConversation(conversationId)}
              onStartNew={startNewChat}
            />

            <div className="glass-panel min-w-0 overflow-hidden flex flex-col">
              <section className="flex items-center justify-between gap-3 border-b border-[var(--line-soft)] px-4 py-2.5">
                <div className="min-w-0">
                  <div className="truncate text-[15px] font-semibold text-[var(--ink)]">
                    {state.conversationTitle || (state.conversationId ? 'Untitled conversation' : 'New chat')}
                  </div>
                  <div className="truncate text-[11px] text-[var(--muted)]">
                    {state.conversationId || (state.conversationsLoading ? 'Refreshing chats…' : `${state.conversations.length} saved chat${state.conversations.length === 1 ? '' : 's'}`)}
                  </div>
                </div>
              </section>

              <div className="flex-1 px-4 py-3">
                {state.turns.length === 0 ? (
                  <div className="k-empty">
                    <div className="k-empty-title">No turns yet</div>
                    <div className="k-empty-body">Ask anything — attachments, web search, and code exec are available.</div>
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {[
                        'Summarize the last attachment as markdown',
                        'Search the web and cite three sources',
                        'Run a small exec report',
                      ].map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          className="k-followup"
                          onClick={() => setState((previous) => ({ ...previous, composerText: prompt }))}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">
                    {state.turns.map((turn) => (
                      <TurnView
                        key={turn.id}
                        turn={turn}
                        sendingDisabled={state.inputLocked || state.connection === 'booting'}
                        onDownloadError={(text) =>
                          setState((previous) => addBanner(previous, 'error', `Download failed: ${text}`))
                        }
                        onFollowup={(text) => {
                          if (state.inputLocked || state.connection === 'booting') return
                          void sendMessage(text, hasPendingTurn ? 'followup' : 'regular')
                        }}
                      />
                    ))}
                  </div>
                )}
                <div ref={bottomRef} />
              </div>

              <div className="border-t border-[var(--line-soft)] px-3 py-3">
                <Composer
                  text={state.composerText}
                  files={state.composerFiles}
                  disabled={state.inputLocked || state.connection === 'booting'}
                  inProgress={hasPendingTurn}
                  lockedMessage={state.inputLockMessage}
                  onTextChange={(value) => setState((previous) => ({ ...previous, composerText: value }))}
                  onFilesAdd={(files) =>
                    setState((previous) => ({
                      ...previous,
                      composerFiles: files ? [...previous.composerFiles, ...Array.from(files)] : previous.composerFiles,
                    }))
                  }
                  onFileRemove={(index) =>
                    setState((previous) => ({
                      ...previous,
                      composerFiles: previous.composerFiles.filter((_, currentIndex) => currentIndex !== index),
                    }))
                  }
                  onSubmit={() => {
                    if (state.inputLocked || state.connection === 'booting') return
                    void sendMessage(undefined, hasPendingTurn ? 'followup' : 'regular')
                  }}
                  onStop={() => {
                    if (state.inputLocked || state.connection === 'booting') return
                    void sendMessage('', 'steer')
                  }}
                />
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
