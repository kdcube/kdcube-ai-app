/**
 * Scene host plumbing that has no React or content dependency: route/runtime
 * context resolution, served-widget URL building, the app operations client,
 * lenient `/profile` probes for the event-driven auth gate, and the
 * CONFIG_REQUEST / CONFIG_RESPONSE handshake (both directions — asking an
 * embedding host for runtime config, and answering child widget frames).
 */

import { asRecord, asString, type SceneComponentSpec } from './registry'

export interface SceneRouteContext {
  tenant: string
  project: string
  bundleId: string
  publicStatic: boolean
  baseUrl: string
  accessToken?: string | null
  idToken?: string | null
}

export interface SceneRuntimeConfigPayload {
  baseUrl?: string
  defaultTenant?: string
  defaultProject?: string
  defaultAppBundleId?: string | null
  tenant?: string
  project?: string
  tenant_id?: string
  project_id?: string
  accessToken?: string | null
  idToken?: string | null
}

function decodePart(value: string | undefined): string {
  if (value === undefined || value === '') return ''
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

/** Resolve tenant/project/app from the page URL (platform bundle routes). */
export function sceneRouteContext(defaultBundleId: string, defaults: { tenant?: string; project?: string } = {}): SceneRouteContext {
  const path = window.location.pathname
  const publicMarker = '/api/integrations/bundles/'
  const staticMarker = '/api/integrations/static/'

  const publicIndex = path.indexOf(publicMarker)
  if (publicIndex >= 0) {
    const parts = path.slice(publicIndex + publicMarker.length).split('/').map(decodePart)
    return {
      tenant: parts[0] ?? '',
      project: parts[1] ?? '',
      bundleId: parts[2] ?? defaultBundleId,
      publicStatic: parts[3] === 'public' && parts[4] === 'static',
      baseUrl: window.location.origin,
    }
  }

  const staticIndex = path.indexOf(staticMarker)
  if (staticIndex >= 0) {
    const parts = path.slice(staticIndex + staticMarker.length).split('/').map(decodePart)
    return {
      tenant: parts[0] ?? '',
      project: parts[1] ?? '',
      bundleId: parts[2] ?? defaultBundleId,
      publicStatic: false,
      baseUrl: window.location.origin,
    }
  }

  const params = new URLSearchParams(window.location.search)
  return {
    tenant: params.get('tenant') ?? defaults.tenant ?? '',
    project: params.get('project') ?? defaults.project ?? '',
    bundleId: params.get('bundle_id') ?? params.get('bundleId') ?? defaultBundleId,
    publicStatic: params.get('public') === '1',
    baseUrl: window.location.origin,
  }
}

export function sceneContextFromConfig(
  config: SceneRuntimeConfigPayload | null,
  fallback: SceneRouteContext,
): SceneRouteContext {
  if (!config) return fallback
  return {
    tenant: config.defaultTenant ?? config.tenant ?? config.tenant_id ?? fallback.tenant,
    project: config.defaultProject ?? config.project ?? config.project_id ?? fallback.project,
    bundleId: config.defaultAppBundleId ?? fallback.bundleId,
    publicStatic: fallback.publicStatic,
    baseUrl: config.baseUrl ?? fallback.baseUrl,
    accessToken: config.accessToken ?? fallback.accessToken,
    idToken: config.idToken ?? fallback.idToken,
  }
}

/**
 * Ask an embedding host for runtime config. Resolves null when the scene is
 * the top window or the host stays silent past the timeout — callers fall
 * back to the URL-derived context.
 */
export function requestSceneRuntimeConfig(identity: string, timeoutMs = 1200): Promise<SceneRuntimeConfigPayload | null> {
  if (window.parent === window) return Promise.resolve(null)
  window.parent.postMessage({ type: 'CONFIG_REQUEST', identity }, '*')
  return new Promise<SceneRuntimeConfigPayload | null>((resolve) => {
    const timer = window.setTimeout(() => {
      window.removeEventListener('message', onMessage)
      resolve(null)
    }, timeoutMs)
    function onMessage(event: MessageEvent): void {
      if (event.data?.type !== 'CONFIG_RESPONSE' && event.data?.type !== 'CONN_RESPONSE') return
      if (event.data.identity !== identity) return
      window.clearTimeout(timer)
      window.removeEventListener('message', onMessage)
      resolve(event.data.config ?? null)
    }
    window.addEventListener('message', onMessage)
  })
}

/**
 * Build the CONFIG_RESPONSE a scene host sends to one of its own widget
 * frames when the scene is the top window. When the scene is itself embedded
 * it should FORWARD the child's CONFIG_REQUEST to its parent instead.
 */
export function buildChildConfigResponse(options: {
  request: Record<string, unknown>
  ctx: SceneRouteContext
  alias: string
  spec?: Pick<SceneComponentSpec, 'bundleId' | 'targetSurfaces'> | null
  surfaceRefPrefix?: string
  namespaceStyles?: Record<string, unknown>
}): { identity: string; config: Record<string, unknown> } | null {
  const identity = asString(asRecord(options.request.data).identity) || asString(options.request.identity)
  if (!identity) return null
  const prefix = options.surfaceRefPrefix || 'scene'
  const config: Record<string, unknown> = {
    configSource: 'scene',
    hostedByScene: true,
    baseUrl: options.ctx.baseUrl,
    defaultTenant: options.ctx.tenant,
    defaultProject: options.ctx.project,
    defaultApp: options.spec?.bundleId || options.ctx.bundleId,
    scene: {
      embedded: true,
      configSource: 'host',
      surface_ref: `${prefix}.${options.alias}`,
      target_surfaces: options.spec?.targetSurfaces ?? [],
      alias: options.alias,
    },
  }
  if (options.namespaceStyles && Object.keys(options.namespaceStyles).length) {
    config.namespace_styles = options.namespaceStyles
    config.namespaceStyles = options.namespaceStyles
  }
  return { identity, config }
}

export function appBaseUrl(ctx: SceneRouteContext, bundleId?: string): string {
  const app = bundleId || ctx.bundleId
  return (
    `${ctx.baseUrl}/api/integrations/bundles/` +
    `${encodeURIComponent(ctx.tenant)}/${encodeURIComponent(ctx.project)}/${encodeURIComponent(app)}`
  )
}

export function widgetUrlForBundle(
  ctx: SceneRouteContext,
  bundleId: string,
  alias: string,
  params?: Record<string, string>,
): string {
  const routePrefix = ctx.publicStatic ? 'public/widgets' : 'widgets'
  const url = new URL(`${appBaseUrl(ctx, bundleId)}/${routePrefix}/${alias}`)
  if (params) {
    Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, value))
  }
  return url.toString()
}

/** URL of a component's served widget (explicit `route` wins over the alias). */
export function componentWidgetUrl(
  ctx: SceneRouteContext,
  spec: Pick<SceneComponentSpec, 'bundleId' | 'widgetAlias' | 'route' | 'params'>,
): string {
  if (spec.route) {
    const route = spec.route.replace(/^\/+/, '')
    const url = new URL(`${appBaseUrl(ctx, spec.bundleId || ctx.bundleId)}/${route}`)
    Object.entries(spec.params ?? {}).forEach(([key, value]) => url.searchParams.set(key, value))
    return url.toString()
  }
  return widgetUrlForBundle(ctx, spec.bundleId || ctx.bundleId, spec.widgetAlias, spec.params)
}

export function operationsUrl(ctx: SceneRouteContext, alias: string): string {
  return `${appBaseUrl(ctx)}/operations/${alias}`
}

export function unwrapOperationResponse<T>(alias: string, payload: unknown): T {
  if (payload && typeof payload === 'object' && alias in payload) {
    return (payload as Record<string, unknown>)[alias] as T
  }
  return payload as T
}

export function operationErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') return fallback
  const direct = payload as Record<string, unknown>
  if (direct.error !== undefined) return String(direct.error)
  if (direct.detail !== undefined) return String(direct.detail)
  if (direct.message !== undefined) return String(direct.message)
  for (const value of Object.values(direct)) {
    if (!value || typeof value !== 'object') continue
    const nested = value as Record<string, unknown>
    if (nested.error !== undefined) return String(nested.error)
    if (nested.detail !== undefined) return String(nested.detail)
    if (nested.message !== undefined) return String(nested.message)
  }
  return fallback
}

export async function postSceneOperation<TReq, TRes>(ctx: SceneRouteContext, alias: string, body: TReq): Promise<TRes> {
  const response = await fetch(operationsUrl(ctx, alias), {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ data: body }),
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(operationErrorMessage(payload, `HTTP ${response.status}`))
  }
  return unwrapOperationResponse<TRes>(alias, payload)
}

export interface SceneProfileIdentity {
  userType: string | null
  userId: string | null
}

/**
 * Lenient `/profile` probe for the auth gate. Tolerates 401/network errors by
 * returning nulls — gated rail entries then stay hidden, the safe fallback.
 * Hosts re-probe on every `kdcube-auth-changed` broadcast; the boot probe is
 * never the only one.
 */
export async function fetchSceneProfileIdentity(ctx: SceneRouteContext): Promise<SceneProfileIdentity> {
  try {
    const response = await fetch(`${ctx.baseUrl}/profile`, {
      method: 'GET',
      credentials: 'include',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return { userType: null, userId: null }
    const payload = (await response.json()) as { user_type?: string | null; user_id?: string | null }
    const userType = String(payload.user_type || '').trim().toLowerCase()
    const userId = String(payload.user_id || '').trim()
    return { userType: userType || null, userId: userId || null }
  } catch {
    return { userType: null, userId: null }
  }
}

export async function fetchSceneProfileSessionId(ctx: SceneRouteContext): Promise<string> {
  const response = await fetch(`${ctx.baseUrl}/profile`, {
    method: 'GET',
    credentials: 'include',
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Unable to fetch profile (${response.status})`)
  }
  const payload = await response.json() as { session_id?: string | null }
  if (!payload.session_id) {
    throw new Error('Profile did not include a session id.')
  }
  return payload.session_id
}
