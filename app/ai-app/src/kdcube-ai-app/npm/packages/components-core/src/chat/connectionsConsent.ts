/**
 * Connected-account consent → Connection-Hub open payload.
 *
 * The backend's consent payload carries a served Connection-Hub deep link
 * (`consent.url`) that encodes the CORRECT view for the deployment — for the
 * delegated-accounts flow that is `?tab=delegated_to_kdcube&provider_id=…&
 * connector_app_id=…&claims=…`, the numbered consent plan. The hub-open
 * payload therefore derives its `tab` and params from that URL verbatim, so
 * the on-scene summon lands on exactly the view the direct link would.
 *
 * URLs that point at the provider-connections cards grant access by claim
 * TIER, so that path also maps the consent's claim ids to the provider's tier
 * ids. Tier vocabulary source of truth: `ConnectionProvider.claim_tiers`
 * (integrations/connections/providers) — Slack: read / write / files,
 * Gmail (provider `google`): read / send.
 */
import type { ConnectionsConsentOpen } from '../shared/index.ts'

const CLAIM_TIERS_BY_PROVIDER: Record<string, Record<string, string>> = {
  slack: {
    'slack:search': 'read',
    'slack:channels': 'read',
    'slack:history': 'read',
    'slack:assistant:search': 'read',
    'slack:post': 'write',
    'slack:files:read': 'files',
    'slack:files:write': 'files',
  },
  google: {
    'gmail:read': 'read',
    'gmail:send': 'send',
  },
}

const PROVIDER_CONNECTIONS_TAB_TOKENS = new Set([
  'provider_connections',
  'provider-connections',
  'providerconnections',
  'providers',
])

/** Provider claim-tier ids covering the given claims (declaration order of
 *  first appearance, deduped). Claims outside the provider's map are omitted. */
export function consentTiersForClaims(provider: string, claims: string[]): string[] {
  const map = CLAIM_TIERS_BY_PROVIDER[String(provider || '').trim().toLowerCase()] || {}
  const tiers: string[] = []
  for (const claim of claims) {
    const tier = map[String(claim || '').trim().toLowerCase()]
    if (tier && !tiers.includes(tier)) tiers.push(tier)
  }
  return tiers
}

/** Parse a served hub deep link into {tab, params}. The link may be
 *  site-relative (`/api/integrations/...?...`); only its query matters here. */
function deepLinkTabAndParams(url: string): { tab: string; params: Record<string, string> } | null {
  const query = url.includes('?') ? url.slice(url.indexOf('?') + 1) : ''
  if (!query) return null
  let search: URLSearchParams
  try {
    search = new URLSearchParams(query)
  } catch {
    return null
  }
  const tab = String(search.get('tab') || '').trim()
  if (!tab) return null
  const params: Record<string, string> = {}
  search.forEach((value, key) => {
    const cleanKey = String(key || '').trim()
    const cleanValue = String(value || '').trim()
    if (cleanKey && cleanKey !== 'tab' && cleanValue) params[cleanKey] = cleanValue
  })
  return { tab, params }
}

/** Build the structured hub-open payload from a consent card's fields.
 *  The consent deep link is authoritative for tab + params; the claim→tier
 *  map fills `tiers` on the provider-connections path. */
export function connectionsConsentOpen(args: {
  provider: string
  claims: string[]
  accountId?: string
  url?: string
}): ConnectionsConsentOpen {
  const url = String(args.url || '').trim()
  const provider = String(args.provider || '').trim()
  const claims = args.claims || []
  const fromUrl = deepLinkTabAndParams(url)
  if (fromUrl) {
    if (PROVIDER_CONNECTIONS_TAB_TOKENS.has(fromUrl.tab.toLowerCase())) {
      if (!fromUrl.params.provider && provider) fromUrl.params.provider = provider
      if (!fromUrl.params.tiers) {
        const tiers = consentTiersForClaims(fromUrl.params.provider || provider, claims)
        if (tiers.length) fromUrl.params.tiers = tiers.join(',')
      }
    }
    return { tab: fromUrl.tab, params: fromUrl.params, url }
  }
  // Deep link without a tab: land on the provider-connections card built from
  // the consent fields.
  const params: Record<string, string> = {}
  if (provider) params.provider = provider
  const tiers = consentTiersForClaims(provider, claims)
  if (tiers.length) params.tiers = tiers.join(',')
  const accountId = String(args.accountId || '').trim()
  if (accountId) params.account_id = accountId
  return { tab: 'provider_connections', params, url }
}
