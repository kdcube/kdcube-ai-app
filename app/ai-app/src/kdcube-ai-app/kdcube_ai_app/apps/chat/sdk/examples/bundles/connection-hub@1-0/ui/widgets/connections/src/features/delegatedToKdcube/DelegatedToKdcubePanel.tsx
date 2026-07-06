import { useMemo, useRef, useState } from 'react';
import { useAppDispatch, useAppSelector } from '../../app/hooks';
import { AccountRow, type AccountStatusTone } from '../../components/AccountRow';
import type { DelegatedToKdcubeAccount, DelegatedToKdcubeClaim, DelegatedToKdcubeProvider } from '../../api/types';
import {
  connectDelegatedToKdcubeCredential,
  disconnectDelegatedToKdcube,
  loadDelegatedToKdcube,
  startDelegatedToKdcubeOAuth,
  type ConnectCredentialArgs,
} from './delegatedToKdcubeSlice';

// Consent payloads deep-link here: ?tab=delegated_to_kdcube&provider_id=…
// &connector_app_id=…&claims=a,b&account_id=… — preselect what the tool
// asked for and highlight the affected account.
interface ConsentDeepLink {
  providerId: string;
  connectorAppId: string;
  claims: string[];
  accountId: string;
}

function consentDeepLinkFromLocation(): ConsentDeepLink {
  const params = new URLSearchParams(window.location.search);
  return {
    providerId: params.get('provider_id') || '',
    connectorAppId: params.get('connector_app_id') || '',
    claims: (params.get('claims') || '').split(',').map((item) => item.trim()).filter(Boolean),
    accountId: params.get('account_id') || '',
  };
}

function providerLabel(provider: DelegatedToKdcubeProvider): string {
  return provider.label || provider.provider_id;
}

function claimLabel(claim: DelegatedToKdcubeClaim | undefined, claimId: string): string {
  return claim?.label || claimId;
}

function accountTitle(account: DelegatedToKdcubeAccount): string {
  return account.display_name || account.email || account.workspace || account.external_subject || account.account_id;
}

function accountSubtitle(account: DelegatedToKdcubeAccount, provider?: DelegatedToKdcubeProvider): string | undefined {
  const bits = [
    provider ? providerLabel(provider) : account.provider_id,
    account.email,
    account.workspace,
    (account.claims || []).join(', '),
  ].filter(Boolean);
  return bits.length ? bits.join(' · ') : undefined;
}

function formatCredentialDate(value?: number): string {
  if (!value) return '';
  try {
    return new Date(value * 1000).toLocaleString();
  } catch {
    return '';
  }
}

function formatIsoDate(value?: string): string {
  if (!value) return '';
  try {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? '' : parsed.toLocaleString();
  } catch {
    return '';
  }
}

function accountLastError(account: DelegatedToKdcubeAccount): string {
  if (!account.last_error) return '';
  const at = formatIsoDate(account.last_error_at);
  return at ? `Last error (${at}): ${account.last_error}` : `Last error: ${account.last_error}`;
}

function accountStatus(account: DelegatedToKdcubeAccount): { label: string; tone: AccountStatusTone; detail: string } {
  const status = account.credential_status || account.status || '';
  const expires = formatCredentialDate(account.credential_expires_at);
  if (status === 'revoked') {
    return {
      label: 'revoked',
      tone: 'error',
      detail: account.credential_message || 'Access was revoked. Reconnect the account if it is still needed.',
    };
  }
  if (account.reconnect_required || status === 'reconnect_required' || status === 'missing') {
    return {
      label: 'reconnect required',
      tone: 'error',
      detail: account.credential_message || 'Reconnect this account before KDCube can use it.',
    };
  }
  if (status === 'refreshable') {
    return {
      label: 'refreshes automatically',
      tone: 'warn',
      detail: account.credential_message || (expires ? `Access expired ${expires}; KDCube will refresh on next use.` : ''),
    };
  }
  if (status === 'expires_soon') {
    return {
      label: 'expires soon',
      tone: 'warn',
      detail: expires ? `Access expires ${expires}.` : (account.credential_message || ''),
    };
  }
  return {
    label: 'connected',
    tone: 'ok',
    detail: expires ? `Access valid until ${expires}.` : (account.credential_message || ''),
  };
}

function firstProviderId(providers: DelegatedToKdcubeProvider[]): string {
  return providers[0]?.provider_id || '';
}

function firstConnectorAppId(provider?: DelegatedToKdcubeProvider): string {
  return Object.values(provider?.connector_apps || {}).find((app) => app.enabled !== false)?.connector_app_id || '';
}

function defaultClaims(provider?: DelegatedToKdcubeProvider, connectorAppId?: string): string[] {
  const app = connectorAppId ? provider?.connector_apps?.[connectorAppId] : undefined;
  const ceiling = app?.allowed_claims || [];
  return ceiling.length ? ceiling : Object.keys(provider?.claims || {});
}

function oauthEnabled(provider?: DelegatedToKdcubeProvider, connectorAppId?: string): boolean {
  const app = connectorAppId ? provider?.connector_apps?.[connectorAppId] : undefined;
  return Boolean(provider?.adapter?.includes('oauth') && app?.client_id);
}

export function DelegatedToKdcubePanel() {
  const dispatch = useAppDispatch();
  const { enabled, providers, accounts, busy } = useAppSelector((s) => s.delegatedToKdcube);
  const providerList = useMemo(
    () => Object.values(providers).filter((provider) => provider.enabled !== false).sort((a, b) => providerLabel(a).localeCompare(providerLabel(b))),
    [providers],
  );
  const [deepLink] = useState<ConsentDeepLink>(consentDeepLinkFromLocation);
  const [providerId, setProviderId] = useState(deepLink.providerId);
  const selectedProviderId = providerId || firstProviderId(providerList);
  const selectedProvider = providers[selectedProviderId];
  const [connectorAppId, setConnectorAppId] = useState(deepLink.providerId ? deepLink.connectorAppId : '');
  const selectedConnectorAppId = connectorAppId || firstConnectorAppId(selectedProvider);
  const claimIds = Object.keys(selectedProvider?.claims || {});
  const suggestedClaims = defaultClaims(selectedProvider, selectedConnectorAppId);
  const [claims, setClaims] = useState<string[]>(deepLink.providerId ? deepLink.claims : []);
  // Deep-links and prefills may carry claims of another provider; only
  // claims this provider declares may reach the OAuth start. If nothing
  // survives the filter, fall back to the provider's suggested claims.
  const rawSelectedClaims = claims.length ? claims : suggestedClaims;
  const providerScopedClaims = claimIds.length
    ? rawSelectedClaims.filter((claimId) => claimIds.includes(claimId))
    : rawSelectedClaims;
  const selectedClaims = providerScopedClaims.length ? providerScopedClaims : suggestedClaims;
  const [email, setEmail] = useState('');
  const [externalSubject, setExternalSubject] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [workspace, setWorkspace] = useState('');
  const [secretKind, setSecretKind] = useState<ConnectCredentialArgs['secretKind']>('app_password');
  const [secretValue, setSecretValue] = useState('');
  const [formNotice, setFormNotice] = useState('');
  const formRef = useRef<HTMLFormElement | null>(null);
  const canStartOAuth = oauthEnabled(selectedProvider, selectedConnectorAppId) && selectedClaims.length > 0;

  const launchOAuth = async (targetProviderId: string, targetConnectorAppId: string, targetClaims: string[]) => {
    const result = await dispatch(startDelegatedToKdcubeOAuth({
      providerId: targetProviderId,
      connectorAppId: targetConnectorAppId,
      claims: targetClaims,
      returnHint: window.location.href,
    })).unwrap().catch(() => undefined);
    if (result?.authorize_url) {
      window.open(result.authorize_url, '_blank', 'noopener,noreferrer');
    }
  };

  // Re-run provider approval for an existing account: same connector app,
  // same claims. OAuth accounts go straight to the provider; credential
  // accounts get the form prefilled so the user pastes a fresh secret.
  const reconnect = (account: DelegatedToKdcubeAccount) => {
    const provider = providers[account.provider_id];
    const appId = account.connector_app_id || firstConnectorAppId(provider);
    const accountClaims = account.claims?.length ? account.claims : defaultClaims(provider, appId);
    if (oauthEnabled(provider, appId)) {
      void launchOAuth(account.provider_id, appId, accountClaims);
      return;
    }
    prefillForAccount(account, accountClaims, 'Enter a fresh credential to reconnect this account.');
  };

  // Claims upgrade: prefill the form with the account's current claims
  // checked so the user adds what is missing, then re-approves.
  const upgradeAccess = (account: DelegatedToKdcubeAccount) => {
    const provider = providers[account.provider_id];
    const appId = account.connector_app_id || firstConnectorAppId(provider);
    const merged = Array.from(new Set([
      ...(account.claims || []),
      ...(deepLink.accountId === account.account_id ? deepLink.claims : []),
    ]));
    prefillForAccount(
      account,
      merged.length ? merged : defaultClaims(provider, appId),
      'Check the additional access this account should approve, then reconnect it.',
    );
  };

  const prefillForAccount = (account: DelegatedToKdcubeAccount, targetClaims: string[], notice: string) => {
    setProviderId(account.provider_id);
    setConnectorAppId(account.connector_app_id || '');
    setClaims(targetClaims);
    setEmail(account.email || '');
    setExternalSubject(account.external_subject || '');
    setDisplayName(account.display_name || '');
    setWorkspace(account.workspace || '');
    setFormNotice(notice);
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const toggleClaim = (claimId: string) => {
    setClaims((current) => {
      const base = current.length ? current : suggestedClaims;
      return base.includes(claimId)
        ? base.filter((item) => item !== claimId)
        : [...base, claimId];
    });
  };

  const changeProvider = (nextProviderId: string) => {
    setProviderId(nextProviderId);
    setConnectorAppId('');
    setClaims([]);
    setFormNotice('');
  };

  const changeConnectorApp = (nextConnectorAppId: string) => {
    setConnectorAppId(nextConnectorAppId);
    setClaims([]);
    setFormNotice('');
  };

  const submit = async () => {
    if (!selectedProviderId || !selectedConnectorAppId || !secretValue || selectedClaims.length === 0) return;
    await dispatch(connectDelegatedToKdcubeCredential({
      providerId: selectedProviderId,
      connectorAppId: selectedConnectorAppId,
      externalSubject,
      email,
      displayName,
      workspace,
      claims: selectedClaims,
      secretKind,
      secretValue,
    })).unwrap().catch(() => undefined);
    setEmail('');
    setExternalSubject('');
    setDisplayName('');
    setWorkspace('');
    setSecretValue('');
    void dispatch(loadDelegatedToKdcube());
  };

  const startOAuth = async () => {
    if (!selectedProviderId || !selectedConnectorAppId || !canStartOAuth) return;
    await launchOAuth(selectedProviderId, selectedConnectorAppId, selectedClaims);
  };

  const disconnect = (accountId: string) => {
    void dispatch(disconnectDelegatedToKdcube({ accountId })).then(() => dispatch(loadDelegatedToKdcube()));
  };

  if (!enabled) {
    return (
      <section className="card">
        <div className="card-head">
          <h2>Delegated to KDCube</h2>
        </div>
        <p className="muted">No external account delegation providers are enabled in this environment.</p>
      </section>
    );
  }

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Delegated to KDCube</h2>
          <p className="muted">
            External accounts this user allows KDCube applications or automation
            to use.
          </p>
        </div>
        <span className="badge badge-ok">{providerList.length} providers</span>
      </div>

      <div className="integration-provider-list">
        {providerList.map((provider) => {
          const providerAccounts = accounts.filter((account) => account.provider_id === provider.provider_id);
          const caps = Object.entries(provider.claims || {});
          return (
            <div className="integration-provider" key={provider.provider_id}>
              <div className="integration-provider-head">
                <div>
                  <div className="account-title">{providerLabel(provider)}</div>
                  {provider.adapter ? <div className="account-sub">{provider.adapter}</div> : null}
                </div>
                <div className="claim-list">
                  {caps.map(([claimId, claim]) => (
                    <span className="claim-chip" key={claimId}>
                      {claimLabel(claim, claimId)}
                    </span>
                  ))}
                </div>
              </div>
              {providerAccounts.length ? (
                <ul className="accounts">
                  {providerAccounts.map((account) => {
                    const status = accountStatus(account);
                    const needsReconnect = status.tone === 'error';
                    return (
                      <AccountRow
                        key={account.account_id}
                        title={accountTitle(account)}
                        subtitle={accountSubtitle(account, provider)}
                        statusLabel={status.label}
                        statusTone={status.tone}
                        detail={status.detail}
                        lastError={needsReconnect ? accountLastError(account) : ''}
                        highlighted={deepLink.accountId === account.account_id}
                        busy={busy}
                        actions={(
                          <>
                            <button
                              className={needsReconnect ? 'btn' : 'btn btn-ghost'}
                              type="button"
                              disabled={busy}
                              onClick={() => reconnect(account)}
                            >
                              Reconnect
                            </button>
                            <button
                              className="btn btn-ghost"
                              type="button"
                              disabled={busy}
                              onClick={() => upgradeAccess(account)}
                            >
                              Add access
                            </button>
                          </>
                        )}
                        onDisconnect={() => disconnect(account.account_id)}
                      />
                    );
                  })}
                </ul>
              ) : (
                <p className="muted">No accounts delegated to KDCube.</p>
              )}
            </div>
          );
        })}
      </div>

      <form
        ref={formRef}
        className="form"
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy) void submit();
        }}
      >
        <div className="form-title">Delegate an account credential to KDCube</div>
        {formNotice ? <p className="notice success">{formNotice}</p> : null}
        <div className="inline-fields">
          <select className="input" value={selectedProviderId} onChange={(event) => changeProvider(event.target.value)}>
            {providerList.map((provider) => (
              <option key={provider.provider_id} value={provider.provider_id}>
                {providerLabel(provider)}
              </option>
            ))}
          </select>
          <select className="input" value={selectedConnectorAppId} onChange={(event) => changeConnectorApp(event.target.value)}>
            {Object.values(selectedProvider?.connector_apps || {}).map((app) => (
              <option key={app.connector_app_id} value={app.connector_app_id}>
                {app.label || app.connector_app_id}
              </option>
            ))}
          </select>
        </div>

        {claimIds.length ? (
          <div className="scope-list">
            {claimIds.map((claimId) => (
              <label className="scope-item" key={claimId}>
                <input
                  type="checkbox"
                  checked={selectedClaims.includes(claimId)}
                  onChange={() => toggleClaim(claimId)}
                  disabled={busy}
                />
                <span>{claimLabel(selectedProvider?.claims?.[claimId], claimId)}</span>
              </label>
            ))}
          </div>
        ) : null}

        {canStartOAuth ? (
          <div className="oauth-connect">
            <button className="btn" type="button" disabled={busy} onClick={() => void startOAuth()}>
              Connect with OAuth
            </button>
            <span className="small">Opens the provider approval page in a new tab.</span>
          </div>
        ) : null}

        <div className="inline-fields">
          <input className="input" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="email" />
          <input className="input" value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="display name" />
        </div>
        <div className="inline-fields">
          <input className="input" value={externalSubject} onChange={(event) => setExternalSubject(event.target.value)} placeholder="provider subject" />
          <input className="input" value={workspace} onChange={(event) => setWorkspace(event.target.value)} placeholder="workspace / mailbox" />
        </div>
        <div className="inline-fields">
          <select className="input" value={secretKind} onChange={(event) => setSecretKind(event.target.value as ConnectCredentialArgs['secretKind'])}>
            <option value="app_password">app password</option>
            <option value="access_token">access token</option>
            <option value="api_key">API key</option>
            <option value="secret">secret</option>
          </select>
          <input
            className="input"
            type="password"
            value={secretValue}
            onChange={(event) => setSecretValue(event.target.value)}
            placeholder="credential"
            autoComplete="new-password"
          />
        </div>
        <button className="btn" type="submit" disabled={busy || !selectedProviderId || !selectedConnectorAppId || !secretValue || selectedClaims.length === 0}>
          Connect
        </button>
      </form>
    </section>
  );
}
