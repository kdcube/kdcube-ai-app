import type { CanvasContextItem } from './contextTypes'

export interface CanvasCard {
  id: string
  kind: string
  title: string
  summary: string
  description?: string
  ref: string
  mime: string
  namespace?: string
  object_kind?: string
  rect: { x: number; y: number; w: number; h: number }
  placement?: 'floating' | 'placed' | 'suggested' | 'trashed'
  trashed?: boolean
  trashState?: Record<string, unknown>
  createdAt?: string
  updatedAt?: string
  selected?: boolean
  suggested?: boolean
  commentsCount?: number
  comments?: CanvasComment[]
}

export interface CanvasComment {
  id: string
  text: string
  actor?: string
  createdAt?: string | number
}

export interface CanvasDefinition {
  id: string
  name: string
  revision: number
  ref: string
  summary: string
  cards: CanvasCard[]
}

export interface CanvasProjection {
  schema: 'kdcube.canvas.projection.v1'
  canvas_id: string
  canvas_name: string
  canvas_uri: string
  revision: number
  bounds: { x: number; y: number; w: number; h: number }
  cards_count: number
  placed_count: number
  floating_count: number
  suggested_count: number
  legend: Array<Record<string, unknown>>
}

export interface CanvasPatchUiEvent {
  type?: string
  source?: string
  canvas_id?: string
  canvas_name?: string
  canvas_uri?: string
  revision?: number
  canvas_ref?: string
  latest_ref?: string
  changed?: unknown[]
  changed_cards?: unknown[]
  projection?: Record<string, unknown>
}

export interface CanvasReadLike {
  canvas_id?: unknown
  canvas_name?: unknown
  revision?: unknown
  canvas_ref?: unknown
  latest_ref?: unknown
  canvas_uri?: unknown
  canvas?: unknown
  projection?: unknown
}

export interface CanvasListItemLike {
  canvas_id?: unknown
  canvas_name?: unknown
  name?: unknown
  latest_revision?: unknown
  revision?: unknown
  latest_ref?: unknown
  canvas_ref?: unknown
  summary?: unknown
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? value as Record<string, unknown> : null
}

function stringValue(value: unknown): string | undefined {
  if (value == null) return undefined
  const text = String(value).trim()
  return text || undefined
}

function canvasNameValue(value: unknown): string {
  return stringValue(value) ?? 'main'
}

function isPlaceholderCanvasId(value: unknown): boolean {
  const id = stringValue(value)
  return !id || id.startsWith('canvas:')
}

function numberValue(value: unknown, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return fallback
}

function optionalNumberValue(value: unknown): number | undefined {
  if (value == null || value === '') return undefined
  const parsed = numberValue(value, NaN)
  return Number.isFinite(parsed) ? parsed : undefined
}

function commentsValue(value: unknown): CanvasComment[] | undefined {
  if (!Array.isArray(value)) return undefined
  const comments = value
    .map((item, index): CanvasComment | null => {
      const raw = asRecord(item)
      if (!raw) {
        const text = stringValue(item)
        return text ? { id: `comment:${index}`, text } : null
      }
      const text = stringValue(raw.text ?? raw.body ?? raw.content)
      if (!text) return null
      return {
        id: stringValue(raw.id ?? raw.comment_id ?? raw.commentId) ?? `comment:${index}`,
        text,
        actor: stringValue(raw.actor ?? raw.author),
        createdAt: optionalNumberValue(raw.created_at ?? raw.createdAt) ?? stringValue(raw.created_at ?? raw.createdAt),
      }
    })
    .filter((comment): comment is CanvasComment => Boolean(comment))
  return comments.length ? comments : undefined
}

function rectValue(value: unknown, index: number): CanvasCard['rect'] {
  const rect = asRecord(value)
  if (!rect) {
    return { x: 420 + (index % 3) * 22, y: 48 + (index % 4) * 72, w: 246, h: 104 }
  }
  return {
    x: numberValue(rect.x, 420 + (index % 3) * 22),
    y: numberValue(rect.y, 48 + (index % 4) * 72),
    w: Math.max(96, numberValue(rect.w, 246)),
    h: Math.max(72, numberValue(rect.h, 104)),
  }
}

export function normalizeCanvasPatchEvent(value: unknown): CanvasPatchUiEvent | null {
  const raw = asRecord(value)
  if (!raw) return null
  const type = stringValue(raw.type)
  if (
    !type ||
    type !== 'canvas.patch.applied' &&
    type !== 'canvas.updated' &&
    !type.endsWith('.canvas.patch.applied') &&
    !type.endsWith('.canvas.updated')
  ) return null
  const changedCards = raw.changed_cards ?? raw.changedCards
  return {
    type,
    source: stringValue(raw.source),
    canvas_id: stringValue(raw.canvas_id ?? raw.canvasId),
    canvas_name: stringValue(raw.canvas_name ?? raw.canvasName),
    canvas_uri: stringValue(raw.canvas_uri ?? raw.canvasUri),
    revision: typeof raw.revision === 'number' ? raw.revision : numberValue(raw.revision, 0),
    canvas_ref: stringValue(raw.canvas_ref ?? raw.canvasRef),
    latest_ref: stringValue(raw.latest_ref ?? raw.latestRef),
    changed: Array.isArray(raw.changed) ? raw.changed : [],
    changed_cards: Array.isArray(changedCards) ? changedCards : [],
    projection: asRecord(raw.projection) ?? undefined,
  }
}

function cardFromProjectionLegendRow(value: unknown, index: number, changedIds: Set<string>): CanvasCard | null {
  const raw = asRecord(value)
  if (!raw) return null
  const id = stringValue(raw.id ?? raw.card_id ?? raw.cardId) ?? `C${index + 1}`
  const kind = stringValue(raw.kind) ?? 'object.ref'
  const ref = stringValue(raw.logical_path ?? raw.logicalPath ?? raw.storage_ref ?? raw.storageRef ?? raw.artifact_ref ?? raw.ref) ?? ''
  const title = stringValue(raw.title ?? raw.label ?? raw.filename) ?? id
  const summary = stringValue(raw.content_preview ?? raw.preview ?? raw.summary ?? raw.description) ?? ''
  const placement = stringValue(raw.placement) as CanvasCard['placement'] | undefined
  const trashed = Boolean(raw.trashed) || placement === 'trashed'
  const changed = changedIds.has(id)
  const comments = commentsValue(raw.comments)
  return {
    id,
    kind,
    title,
    summary,
    description: stringValue(raw.description),
    ref,
    mime: stringValue(raw.mime) ?? 'application/json',
    namespace: stringValue(raw.namespace),
    object_kind: stringValue(raw.object_kind ?? raw.objectKind),
    rect: rectValue(raw.rect, index),
    placement,
    trashed,
    trashState: asRecord(raw.trash_state ?? raw.trashState) ?? undefined,
    createdAt: stringValue(raw.created_at ?? raw.createdAt ?? raw.ts),
    updatedAt: stringValue(raw.updated_at ?? raw.updatedAt),
    selected: Boolean(raw.selected) || changed,
    suggested: Boolean(raw.suggested) || placement === 'suggested',
    commentsCount: optionalNumberValue(raw.comments_count ?? raw.commentsCount) ??
      comments?.length,
    comments,
  }
}

export function cardsFromProjection(projection: unknown, changedCards: unknown[] = []): CanvasCard[] {
  const rawProjection = asRecord(projection)
  const legend = Array.isArray(rawProjection?.legend) ? rawProjection.legend : []
  const changedIds = new Set(
    changedCards
      .map((value) => {
        const raw = asRecord(value)
        return stringValue(raw?.id ?? raw?.card_id ?? raw?.cardId)
      })
      .filter((value): value is string => Boolean(value)),
  )
  return legend
    .map((row, index) => cardFromProjectionLegendRow(row, index, changedIds))
    .filter((card): card is CanvasCard => Boolean(card))
}

function isFullCanvasProjection(projection: unknown, projectedCardCount: number): boolean {
  const rawProjection = asRecord(projection)
  const schema = stringValue(rawProjection?.schema)
  const cardsCount = optionalNumberValue(rawProjection?.cards_count ?? rawProjection?.cardsCount)
  return schema === 'kdcube.canvas.projection.v1' &&
    cardsCount !== undefined &&
    cardsCount === projectedCardCount
}

export function emptyCanvasDefinition(name = 'main', canvasId = ''): CanvasDefinition {
  const canvasName = canvasNameValue(name)
  const id = stringValue(canvasId) ?? `cnv:${canvasName}`
  return {
    id,
    name: canvasName,
    revision: 0,
    ref: `cnv:${canvasName}`,
    summary: 'Empty canvas. Add text, attachments, namespace refs, memories, files, or assistant suggestions.',
    cards: [],
  }
}

export function canvasFromListItem(item: CanvasListItemLike): CanvasDefinition {
  const name = canvasNameValue(item.canvas_name ?? item.name)
  const id = stringValue(item.canvas_id) ?? `cnv:${name}`
  const revision = numberValue(item.latest_revision ?? item.revision, 0)
  return {
    id,
    name,
    revision,
    ref: stringValue(item.latest_ref ?? item.canvas_ref) ?? `cnv:${name}`,
    summary: stringValue(item.summary) ?? `${name} canvas, revision ${revision}`,
    cards: [],
  }
}

export function canvasFromReadResponse(
  response: CanvasReadLike,
  fallback: CanvasDefinition = emptyCanvasDefinition(),
): CanvasDefinition {
  const rawCanvas = asRecord(response.canvas)
  const name = stringValue(
    response.canvas_name ?? rawCanvas?.canvas_name ?? rawCanvas?.name ?? fallback.name,
  ) ?? fallback.name
  const id = stringValue(response.canvas_id ?? rawCanvas?.canvas_id ?? fallback.id) ?? fallback.id
  const revision = numberValue(response.revision ?? rawCanvas?.revision, fallback.revision)
  const cardsFromFullProjection = cardsFromProjection(response.projection)
  const rawCards = Array.isArray(rawCanvas?.cards) ? rawCanvas.cards : []
  const rawCommentsByCardId = new Map<string, CanvasComment[]>()
  rawCards.forEach((value) => {
    const raw = asRecord(value)
    if (!raw) return
    const id = stringValue(raw.id ?? raw.card_id ?? raw.cardId)
    if (!id) return
    const comments = commentsValue(raw.comments)
    if (comments?.length) rawCommentsByCardId.set(id, comments)
  })
  const cards = (cardsFromFullProjection.length ? cardsFromFullProjection : fallback.cards).map((card) => {
    const comments = card.comments?.length ? card.comments : rawCommentsByCardId.get(card.id)
    return comments?.length
      ? { ...card, comments, commentsCount: card.commentsCount ?? comments.length }
      : card
  })
  return {
    id,
    name,
    revision,
    ref: stringValue(response.latest_ref ?? response.canvas_ref ?? response.canvas_uri) ?? fallback.ref,
    summary: cards.length
      ? `${cards.length} canvas pin${cards.length === 1 ? '' : 's'} loaded from bundle storage.`
      : 'Empty canvas loaded from bundle storage.',
    cards,
  }
}

export function canvasFromPatchEvent(
  event: CanvasPatchUiEvent,
  fallback: CanvasDefinition = emptyCanvasDefinition(event.canvas_name || 'main', event.canvas_id || ''),
): CanvasDefinition {
  const changedCards = cardsFromPatchEvent(event)
  const projectionCards = cardsFromProjection(event.projection, event.changed_cards)
  const fullProjection = isFullCanvasProjection(event.projection, projectionCards.length)
  const cards = fullProjection
    ? projectionCards
    : (() => {
      const incomingCards = changedCards.length ? changedCards : projectionCards
      const mergedCards = new Map(fallback.cards.map((card) => [card.id, card]))
      incomingCards.forEach((card) => {
        const existing = mergedCards.get(card.id)
        mergedCards.set(card.id, {
          ...existing,
          ...card,
          rect: existing ? { ...existing.rect, ...card.rect } : card.rect,
          selected: card.selected || existing?.selected,
          suggested: card.suggested ?? existing?.suggested,
        })
      })
      return Array.from(mergedCards.values())
    })()
  return {
    id: event.canvas_id || fallback.id,
    name: event.canvas_name || fallback.name,
    revision: typeof event.revision === 'number' ? event.revision : fallback.revision,
    ref: event.latest_ref || event.canvas_ref || event.canvas_uri || fallback.ref,
    summary: cards.length
      ? `${cards.length} canvas pin${cards.length === 1 ? '' : 's'} after latest patch.`
      : fallback.summary,
    cards,
  }
}

export function upsertCanvasDefinition(
  canvases: CanvasDefinition[],
  canvas: CanvasDefinition,
): CanvasDefinition[] {
  const next: CanvasDefinition[] = []
  for (const item of [...canvases, canvas]) {
    const itemName = canvasNameValue(item.name)
    const index = next.findIndex((existing) => canvasNameValue(existing.name) === itemName || existing.id === item.id)
    if (index < 0) {
      next.push({ ...item, name: itemName })
      continue
    }
    const existing = next[index]
    const existingPlaceholder = isPlaceholderCanvasId(existing.id)
    const itemPlaceholder = isPlaceholderCanvasId(item.id)
    const preferred = !itemPlaceholder || existingPlaceholder ? item : existing
    const fallback = preferred === item ? existing : item
    next[index] = {
      ...fallback,
      ...preferred,
      name: itemName,
      id: stringValue(preferred.id) ?? stringValue(fallback.id) ?? `cnv:${itemName}`,
      ref: stringValue(preferred.ref) ?? stringValue(fallback.ref) ?? `cnv:${itemName}`,
      cards: preferred.cards.length || !fallback.cards.length ? preferred.cards : fallback.cards,
    }
  }
  return next
}

export function findCanvas(canvases: CanvasDefinition[], name: string): CanvasDefinition {
  return canvases.find((canvas) => canvas.name === name) ??
    canvases.find((canvas) => canvas.id === name) ??
    emptyCanvasDefinition(name)
}

export function cardsFromPatchEvent(event: CanvasPatchUiEvent): CanvasCard[] {
  const rawCards = Array.isArray(event.changed_cards) ? event.changed_cards : []
  return rawCards.map((value, index): CanvasCard | null => {
    const raw = asRecord(value)
    if (!raw) return null
    const id = stringValue(raw.id ?? raw.card_id ?? raw.cardId) ?? `R${Date.now()}_${index}`
    const kind = stringValue(raw.kind) ?? 'agent.text'
    const ref = stringValue(raw.logical_path ?? raw.logicalPath ?? raw.storage_ref ?? raw.storageRef ?? raw.artifact_ref ?? raw.ref) ?? ''
    const title = stringValue(raw.title ?? raw.label ?? raw.filename) ?? id
    const summary = stringValue(raw.content_preview ?? raw.preview ?? raw.summary ?? raw.description) ?? ''
    const placement = stringValue(raw.placement) as CanvasCard['placement'] | undefined
    const trashed = Boolean(raw.trashed) || placement === 'trashed'
    return {
      id,
      kind,
      title,
      summary,
      description: stringValue(raw.description),
      ref,
      mime: stringValue(raw.mime) ?? 'text/plain',
      namespace: stringValue(raw.namespace),
      object_kind: stringValue(raw.object_kind ?? raw.objectKind),
      rect: rectValue(raw.rect, index),
      placement,
      trashed,
      trashState: asRecord(raw.trash_state ?? raw.trashState) ?? undefined,
      createdAt: stringValue(raw.created_at ?? raw.createdAt ?? raw.ts),
      updatedAt: stringValue(raw.updated_at ?? raw.updatedAt),
      selected: true,
      suggested: Boolean(raw.suggested) || placement === 'suggested',
    commentsCount: optionalNumberValue(raw.comments_count ?? raw.commentsCount) ??
      commentsValue(raw.comments)?.length,
    comments: commentsValue(raw.comments),
  }
  }).filter((card): card is CanvasCard => Boolean(card))
}

function canvasBounds(cards: CanvasCard[]): CanvasProjection['bounds'] {
  const maxRight = cards.reduce((value, card) => Math.max(value, card.rect.x + card.rect.w), 1600)
  const maxBottom = cards.reduce((value, card) => Math.max(value, card.rect.y + card.rect.h), 1000)
  return {
    x: 0,
    y: 0,
    w: Math.max(1600, Math.ceil(maxRight + 80)),
    h: Math.max(1000, Math.ceil(maxBottom + 80)),
  }
}

function cardMapPrefix(card: CanvasCard): string {
  const source = cleanNamespaceValue(card.object_kind) || cleanNamespaceValue(card.namespace)
  if (!source) return 'O'
  const parts = source.split(/[^a-z0-9]+/i).filter(Boolean)
  if (!parts.length) return 'O'
  if (parts.length === 1) return parts[0].slice(0, 3).toUpperCase()
  return parts.map((part) => part.slice(0, 1).toUpperCase()).join('').slice(0, 4) || 'O'
}

export function canvasProjection(canvas: CanvasDefinition): CanvasProjection {
  const counters = new Map<string, number>()
  const legend = canvas.cards.map((card) => ({
    id: card.id,
    map_label: (() => {
      const prefix = cardMapPrefix(card)
      const next = (counters.get(prefix) || 0) + 1
      counters.set(prefix, next)
      return `${prefix}${next}`
    })(),
    kind: card.kind,
    title: card.title,
    mime: card.mime,
    namespace: cleanNamespaceValue(card.namespace),
    object_kind: cleanNamespaceValue(card.object_kind),
    content_preview: card.summary,
    description: card.description,
    content_size: undefined,
    placement: card.placement || 'placed',
    rect: card.rect,
    logical_path: card.ref,
    selected: Boolean(card.selected),
    suggested: Boolean(card.suggested) || card.placement === 'suggested',
    comments_count: card.commentsCount,
    comments: card.comments,
  }))
  return {
    schema: 'kdcube.canvas.projection.v1',
    canvas_id: canvas.id,
    canvas_name: canvas.name,
    canvas_uri: `cnv:${canvas.name}@${canvas.revision}`,
    revision: canvas.revision,
    bounds: canvasBounds(canvas.cards),
    cards_count: canvas.cards.length,
    placed_count: canvas.cards.filter((card) => card.placement !== 'floating' && card.placement !== 'suggested').length,
    floating_count: canvas.cards.filter((card) => card.placement === 'floating').length,
    suggested_count: canvas.cards.filter((card) => card.suggested || card.placement === 'suggested').length,
    legend,
  }
}

export function canvasContext(canvas: CanvasDefinition): CanvasContextItem {
  const projection = canvasProjection(canvas)
  const selectedCards = canvas.cards.filter((card) => card.selected)
  return {
    id: canvas.id,
    kind: 'canvas',
    label: `Canvas: ${canvas.name}`,
    summary: canvas.summary,
    ref: canvas.ref,
    logical_path: canvas.ref,
    mime: 'application/vnd.kdcube.canvas+json;version=1',
    canvas_id: canvas.id,
    canvas_name: canvas.name,
    revision: canvas.revision,
    data: {
      card_count: canvas.cards.length,
      selected_card_ids: selectedCards.map((card) => card.id),
      focused_cards: selectedCards.map((card) => cardContext(canvas, card)),
      projection,
    },
  }
}

function cleanNamespaceValue(value?: string): string | undefined {
  const text = String(value || '').trim().toLowerCase()
  return text || undefined
}

function proxiedCardKind(card: CanvasCard): string {
  return card.kind || 'object.ref'
}

export function cardContext(canvas: CanvasDefinition, card: CanvasCard): CanvasContextItem {
  const ref = String(card.ref || '').trim()
  const cardKind = proxiedCardKind(card)
  const namespace = cleanNamespaceValue(card.namespace)
  const objectKind = cleanNamespaceValue(card.object_kind)
  return {
    id: ref || `${canvas.id}:${card.id}:r${canvas.revision}`,
    kind: cardKind,
    label: `${card.id} ${card.title}`,
    summary: card.summary,
    ref,
    namespace,
    object_kind: objectKind,
    logical_path: ref,
    mime: card.mime,
    canvas_id: canvas.id,
    canvas_name: canvas.name,
    revision: canvas.revision,
    card_id: card.id,
    card_type: card.kind,
    selected: card.selected,
    data: {
      namespace,
      object_kind: objectKind,
      object_ref: ref || undefined,
      title: card.title,
      canvas_context: {
        canvas_id: canvas.id,
        canvas_name: canvas.name,
        revision: canvas.revision,
        card_id: card.id,
        card_kind: card.kind,
        rect: card.rect,
        selected: Boolean(card.selected),
      },
    },
  }
}
