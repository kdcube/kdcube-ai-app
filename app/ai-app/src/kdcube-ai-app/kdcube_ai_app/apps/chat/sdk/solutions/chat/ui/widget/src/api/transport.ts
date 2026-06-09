/**
 * Low-level HTTP/transport helpers shared by `./client.ts` and
 * `./sseTransport.ts`.
 *
 * Moved verbatim from src/service.ts (Wave 4). Includes:
 *  - buildRequestHeaders (adds timezone + auth)
 *  - resolveAbsoluteUrl (resolves relative paths against settings.getBaseUrl)
 *  - downloadBlobAsFile (programmatic anchor download)
 *  - requireScope (returns {tenant, project}, throws when unset)
 *  - fetchProfileSessionId (lazy session id resolver)
 */

import { BUILT_BUNDLE_ID, getClientTimezone, isStandaloneDevChat, makeAuthHeaders, settings } from '../settings.ts'

export function buildRequestHeaders(base?: HeadersInit): Headers {
  const headers = makeAuthHeaders(base)
  const tz = getClientTimezone()
  if (tz.tz) headers.set('X-User-Timezone', tz.tz)
  headers.set('X-User-UTC-Offset', String(tz.utcOffsetMin))
  return headers
}

export function resolveAbsoluteUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  const base = settings.getBaseUrl()
  return `${base}${path.startsWith('/') ? path : `/${path}`}`
}

export function downloadBlobAsFile(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function requireScope(): { tenant: string; project: string } {
  const tenant = settings.getTenant()
  const project = settings.getProject()
  if (!tenant || !project) {
    throw new Error('Tenant/project is not configured for this bundle UI.')
  }
  return { tenant, project }
}

/** Compose the canonical URL the platform serves a bundle widget at:
 *  `GET /api/integrations/bundles/{tenant}/{project}/{bundle_id}/widgets/{alias}`.
 *  Used by the main UI to iframe a sibling bundle widget in
 *  the side pane. */
export function bundleWidgetUrl(alias: string): string {
  const { tenant, project } = requireScope()
  const bundleId = settings.getBundleId() || BUILT_BUNDLE_ID
  return `${settings.getBaseUrl()}/api/integrations/bundles/${encodeURIComponent(tenant)}/${encodeURIComponent(project)}/${encodeURIComponent(bundleId)}/widgets/${encodeURIComponent(alias)}`
}

export async function fetchProfileSessionId(sessionId?: string | null): Promise<string> {
  if (sessionId) return sessionId
  return (await fetchProfile()).sessionId
}

export interface ProfileInfo {
  sessionId: string
  /** Server-authoritative identity. `'anonymous'` for unauthenticated
   *  visitors; an authenticated user type otherwise. May be null if the
   *  server omits it. */
  userType: string | null
  roles: string[]
}

/** Fetch the server profile. The server is the source of truth for
 *  whether the caller is anonymous — the public landing renders this
 *  chat for everyone, but only an authenticated profile may open the
 *  stream and send. */
export async function fetchProfile(): Promise<ProfileInfo> {
  if (isStandaloneDevChat()) {
    return {
      sessionId: 'standalone-dev-session',
      userType: 'anonymous',
      roles: [],
    }
  }
  const response = await fetch(`${settings.getBaseUrl()}/profile`, {
    method: 'GET',
    credentials: 'include',
    headers: buildRequestHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText)
    throw new Error(`Unable to fetch profile (${response.status}): ${detail}`)
  }

  const data = (await response.json()) as {
    session_id?: string | null
    user_type?: string | null
    roles?: unknown
  }
  if (!data.session_id) {
    throw new Error('Profile did not include a session id.')
  }
  return {
    sessionId: data.session_id,
    userType: data.user_type ?? null,
    roles: Array.isArray(data.roles) ? data.roles.filter((r): r is string => typeof r === 'string') : [],
  }
}
