type ContextLike = Record<string, unknown>

export interface NamespaceVisualStyle {
  label?: string
  color?: string
  ink?: string
  border?: string
  focus?: string
  background?: string
}

export type NamespaceStyleMap = Record<string, unknown>
export type NamespaceStyleVars = Record<`--${string}`, string>

function asContextLike(value: unknown): ContextLike {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as ContextLike : {}
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function safeClass(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function objectRef(context: ContextLike): string {
  const data = context.data && typeof context.data === 'object' ? context.data as ContextLike : {}
  const keys = ['ref', 'object_ref', 'objectRef', 'logicalPath', 'logical_path', 'hostedUri', 'hosted_uri', 'event_ref', 'uri', 'canonical_uri']
  for (const key of keys) {
    const value = text(context[key])
    if (value) return value
  }
  for (const key of keys) {
    const value = text(data[key])
    if (value) return value
  }
  return ''
}

function namespaceClassesFromRef(ref: string): string[] {
  const clean = ref.split(/[?#]/, 1)[0].trim().toLowerCase()
  if (!clean || !clean.includes(':')) return []
  const parts = clean.split(':').filter(Boolean).map(safeClass).filter(Boolean)
  if (!parts.length) return []
  const classes = [parts[0]]
  if (parts.length > 1) classes.push(`${parts[0]}-${parts[1]}`)
  return classes
}

function rootNamespace(value: string): string {
  return safeClass(value.split(':', 1)[0] || '')
}

function namespaceFromRef(ref: string): string {
  const clean = ref.split(/[?#]/, 1)[0].trim()
  const index = clean.indexOf(':')
  return index > 0 ? rootNamespace(clean.slice(0, index)) : ''
}

export function contextNamespace(context: unknown): string {
  const item = asContextLike(context)
  const data = asContextLike(item.data)
  const explicit = rootNamespace(text(item.namespace))
  if (explicit) return explicit
  const nested = rootNamespace(text(data.namespace))
  if (nested) return nested
  return namespaceFromRef(objectRef(item))
}

function styleFromRaw(value: unknown): NamespaceVisualStyle | null {
  if (typeof value === 'string' && value.trim()) return { color: value.trim() }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as NamespaceVisualStyle
}

export function namespaceStyleVars(
  namespace: string,
  namespaceStyles: NamespaceStyleMap = {},
): NamespaceStyleVars | undefined {
  const root = rootNamespace(namespace)
  if (!root) return undefined
  const style = styleFromRaw(namespaceStyles[root])
  if (!style) return undefined
  const ink = style.ink || style.color
  const border = style.border || style.color
  const focus = style.focus || style.color
  const background = style.background
  const vars: NamespaceStyleVars = {}
  if (ink) {
    vars['--ctx-ink'] = ink
    vars['--ns-ink'] = ink
  }
  if (border) {
    vars['--ctx-border'] = border
    vars['--ns-border'] = border
  }
  if (focus) {
    vars['--ctx-focus'] = focus
    vars['--ns-focus'] = focus
  }
  if (background) {
    vars['--ctx-bg'] = background
    vars['--ns-bg'] = background
  }
  return Object.keys(vars).length ? vars : undefined
}

export function contextChipStyle(
  context: unknown,
  namespaceStyles: NamespaceStyleMap = {},
): NamespaceStyleVars | undefined {
  return namespaceStyleVars(contextNamespace(context), namespaceStyles)
}

export function contextChipClass(context: unknown): string {
  const item = asContextLike(context)
  const data = asContextLike(item.data)
  const ref = objectRef(item)
  const classes = [
    text(item.kind),
    text(item.cardType),
    text(item.card_type),
    text(item.namespace),
    text(item.object_kind),
    text(data.namespace),
    text(data.object_kind),
    ...namespaceClassesFromRef(ref),
  ]
  return Array.from(new Set(classes.map(safeClass).filter(Boolean))).join(' ')
}
