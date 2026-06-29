import { UserManager, type UserManagerSettings } from 'oidc-client-ts';
import { settings } from './settings';

type FrontendAuthConfig = {
  authType?: string;
  oidcConfig?: Record<string, unknown>;
  authTokenCookieName?: string;
  idTokenCookieName?: string;
};

type FrontendConfig = {
  auth?: FrontendAuthConfig;
  routesPrefix?: string;
};

let configPromise: Promise<FrontendConfig | null> | null = null;
const FORCE_PROMPT_KEY = 'connection_hub_force_platform_login_prompt';

function normalizePrefix(value: unknown): string {
  const raw = String(value || '/platform').trim() || '/platform';
  const prefixed = raw.startsWith('/') ? raw : `/${raw}`;
  return prefixed.replace(/\/+$/, '') || '/platform';
}

function oidcString(config: Record<string, unknown>, key: string): string {
  return typeof config[key] === 'string' ? String(config[key]) : '';
}

function rememberForcePrompt() {
  try {
    window.sessionStorage.setItem(FORCE_PROMPT_KEY, '1');
  } catch {
    // ignore storage failures; sign-in still works without forced account choice
  }
  try {
    window.localStorage.setItem(FORCE_PROMPT_KEY, '1');
  } catch {
    // ignore storage failures; sign-in still works without forced account choice
  }
}

function takeForcePrompt(): boolean {
  let requested = false;
  try {
    requested = window.sessionStorage.getItem(FORCE_PROMPT_KEY) === '1' || requested;
    window.sessionStorage.removeItem(FORCE_PROMPT_KEY);
  } catch {
    // ignore storage failures
  }
  try {
    requested = window.localStorage.getItem(FORCE_PROMPT_KEY) === '1' || requested;
    window.localStorage.removeItem(FORCE_PROMPT_KEY);
  } catch {
    // ignore storage failures
  }
  return requested;
}

function expireCookie(name: string) {
  if (!name) return;
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `${encodeURIComponent(name)}=; Max-Age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax${secure}`;
}

function clearPlatformCookies(config: FrontendConfig | null) {
  const auth = config?.auth || {};
  expireCookie(auth.authTokenCookieName || '__Secure-LATC');
  expireCookie(auth.idTokenCookieName || '__Secure-LITC');
}

async function loadFrontendConfig(): Promise<FrontendConfig | null> {
  if (!configPromise) {
    configPromise = (async () => {
      const response = await fetch(`${settings.getBaseUrl()}/api/cp-frontend-config`, {
        credentials: 'include',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) return null;
      return await response.json() as FrontendConfig;
    })().catch(() => null);
  }
  return configPromise;
}

function userManagerSettings(config: FrontendConfig): UserManagerSettings | null {
  const auth = config.auth || {};
  const authType = String(auth.authType || '').toLowerCase();
  if (authType !== 'cognito' && authType !== 'oauth') return null;
  const oidc = auth.oidcConfig || {};
  const authority = oidcString(oidc, 'authority');
  const clientId = oidcString(oidc, 'client_id') || oidcString(oidc, 'clientId');
  if (!authority || !clientId) return null;
  const routePrefix = normalizePrefix(config.routesPrefix);
  const redirectUri = oidcString(oidc, 'redirect_uri') || `${window.location.origin}${routePrefix}/callback`;
  const scope = oidcString(oidc, 'scope') || 'openid email phone profile';
  return {
    ...oidc,
    authority,
    client_id: clientId,
    redirect_uri: redirectUri,
    post_logout_redirect_uri: `${window.location.origin}${routePrefix}/chat`,
    response_type: 'code',
    scope,
    automaticSilentRenew: false,
    monitorSession: false,
    loadUserInfo: true,
  };
}

export async function startPlatformSignIn(returnTo = window.location.href): Promise<boolean> {
  const config = await loadFrontendConfig();
  if (!config) return false;
  const managerSettings = userManagerSettings(config);
  if (!managerSettings) return false;
  const manager = new UserManager(managerSettings);
  await manager.clearStaleState().catch(() => undefined);
  const redirectArgs: Parameters<UserManager['signinRedirect']>[0] = {
    state: JSON.stringify({ navigateTo: returnTo }),
  };
  if (takeForcePrompt()) {
    redirectArgs.prompt = 'select_account';
    redirectArgs.extraQueryParams = {
      ...(redirectArgs.extraQueryParams || {}),
      max_age: '0',
    };
  }
  await manager.signinRedirect(redirectArgs);
  return true;
}

export async function signOutPlatformSession(): Promise<void> {
  const config = await loadFrontendConfig();
  const managerSettings = config ? userManagerSettings(config) : null;
  if (managerSettings) {
    const manager = new UserManager(managerSettings);
    await manager.removeUser().catch(() => undefined);
    await manager.clearStaleState().catch(() => undefined);
  }
  clearPlatformCookies(config);
  rememberForcePrompt();
  window.dispatchEvent(new CustomEvent('kdcube-auth-changed', {
    detail: {
      ready: true,
      authenticated: false,
      reason: 'connection-hub-platform-session-cleared',
    },
  }));
}
