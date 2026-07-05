import { useMemo, useState } from 'react';
import { useAppDispatch, useAppSelector } from '../../app/hooks';
import { AccountRow } from '../../components/AccountRow';
import type { UserIntegrationAccount, UserIntegrationCapability, UserIntegrationProvider } from '../../api/types';
import {
  connectUserIntegrationCredential,
  disconnectUserIntegration,
  loadUserIntegrations,
  startUserIntegrationOAuth,
  type ConnectCredentialArgs,
} from './userIntegrationsSlice';

function providerLabel(provider: UserIntegrationProvider): string {
  return provider.label || provider.provider_id;
}

function capabilityLabel(capability: UserIntegrationCapability | undefined, capabilityId: string): string {
  return capability?.label || capabilityId;
}

function accountTitle(account: UserIntegrationAccount): string {
  return account.display_name || account.email || account.workspace || account.external_subject || account.account_id;
}

function accountSubtitle(account: UserIntegrationAccount, provider?: UserIntegrationProvider): string | undefined {
  const bits = [
    provider ? providerLabel(provider) : account.provider_id,
    account.email,
    account.workspace,
    (account.capabilities || []).join(', '),
  ].filter(Boolean);
  return bits.length ? bits.join(' · ') : undefined;
}

function firstProviderId(providers: UserIntegrationProvider[]): string {
  return providers[0]?.provider_id || '';
}

function firstConnectorAppId(provider?: UserIntegrationProvider): string {
  return Object.values(provider?.connector_apps || {}).find((app) => app.enabled !== false)?.app_id || '';
}

function defaultCapabilities(provider?: UserIntegrationProvider, appId?: string): string[] {
  const app = appId ? provider?.connector_apps?.[appId] : undefined;
  const ceiling = app?.capability_ceiling || [];
  return ceiling.length ? ceiling : Object.keys(provider?.capabilities || {});
}

function oauthEnabled(provider?: UserIntegrationProvider, appId?: string): boolean {
  const app = appId ? provider?.connector_apps?.[appId] : undefined;
  return Boolean(provider?.adapter?.includes('oauth') && app?.client_id);
}

export function UserIntegrationsPanel() {
  const dispatch = useAppDispatch();
  const { enabled, providers, accounts, busy } = useAppSelector((s) => s.userIntegrations);
  const providerList = useMemo(
    () => Object.values(providers).filter((provider) => provider.enabled !== false).sort((a, b) => providerLabel(a).localeCompare(providerLabel(b))),
    [providers],
  );
  const [providerId, setProviderId] = useState('');
  const selectedProviderId = providerId || firstProviderId(providerList);
  const selectedProvider = providers[selectedProviderId];
  const [appId, setAppId] = useState('');
  const selectedAppId = appId || firstConnectorAppId(selectedProvider);
  const capabilityIds = Object.keys(selectedProvider?.capabilities || {});
  const suggestedCapabilities = defaultCapabilities(selectedProvider, selectedAppId);
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const selectedCapabilities = capabilities.length ? capabilities : suggestedCapabilities;
  const [email, setEmail] = useState('');
  const [externalSubject, setExternalSubject] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [workspace, setWorkspace] = useState('');
  const [secretKind, setSecretKind] = useState<ConnectCredentialArgs['secretKind']>('app_password');
  const [secretValue, setSecretValue] = useState('');
  const canStartOAuth = oauthEnabled(selectedProvider, selectedAppId) && selectedCapabilities.length > 0;

  const toggleCapability = (capabilityId: string) => {
    setCapabilities((current) => {
      const base = current.length ? current : suggestedCapabilities;
      return base.includes(capabilityId)
        ? base.filter((item) => item !== capabilityId)
        : [...base, capabilityId];
    });
  };

  const changeProvider = (nextProviderId: string) => {
    setProviderId(nextProviderId);
    setAppId('');
    setCapabilities([]);
  };

  const changeApp = (nextAppId: string) => {
    setAppId(nextAppId);
    setCapabilities([]);
  };

  const submit = async () => {
    if (!selectedProviderId || !secretValue || selectedCapabilities.length === 0) return;
    await dispatch(connectUserIntegrationCredential({
      provider: selectedProviderId,
      appId: selectedAppId || undefined,
      externalSubject,
      email,
      displayName,
      workspace,
      capabilities: selectedCapabilities,
      secretKind,
      secretValue,
    })).unwrap().catch(() => undefined);
    setEmail('');
    setExternalSubject('');
    setDisplayName('');
    setWorkspace('');
    setSecretValue('');
    void dispatch(loadUserIntegrations());
  };

  const startOAuth = async () => {
    if (!selectedProviderId || !canStartOAuth) return;
    const result = await dispatch(startUserIntegrationOAuth({
      provider: selectedProviderId,
      appId: selectedAppId || undefined,
      capabilities: selectedCapabilities,
      returnHint: window.location.href,
    })).unwrap().catch(() => undefined);
    if (result?.authorize_url) {
      window.open(result.authorize_url, '_blank', 'noopener,noreferrer');
    }
  };

  const disconnect = (accountId: string) => {
    void dispatch(disconnectUserIntegration({ accountId })).then(() => dispatch(loadUserIntegrations()));
  };

  if (!enabled) {
    return (
      <section className="card">
        <div className="card-head">
          <h2>User integrations</h2>
        </div>
        <p className="muted">No user integrations are enabled in this environment.</p>
      </section>
    );
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>User integrations</h2>
        <span className="badge badge-ok">{providerList.length} providers</span>
      </div>

      <div className="integration-provider-list">
        {providerList.map((provider) => {
          const providerAccounts = accounts.filter((account) => account.provider_id === provider.provider_id);
          const caps = Object.entries(provider.capabilities || {});
          return (
            <div className="integration-provider" key={provider.provider_id}>
              <div className="integration-provider-head">
                <div>
                  <div className="account-title">{providerLabel(provider)}</div>
                  {provider.adapter ? <div className="account-sub">{provider.adapter}</div> : null}
                </div>
                <div className="capability-list">
                  {caps.map(([capabilityId, capability]) => (
                    <span className="capability-chip" key={capabilityId}>
                      {capabilityLabel(capability, capabilityId)}
                    </span>
                  ))}
                </div>
              </div>
              {providerAccounts.length ? (
                <ul className="accounts">
                  {providerAccounts.map((account) => (
                    <AccountRow
                      key={account.account_id}
                      title={accountTitle(account)}
                      subtitle={accountSubtitle(account, provider)}
                      busy={busy}
                      onDisconnect={() => disconnect(account.account_id)}
                    />
                  ))}
                </ul>
              ) : (
                <p className="muted">No connected accounts.</p>
              )}
            </div>
          );
        })}
      </div>

      <form
        className="form"
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy) void submit();
        }}
      >
        <div className="form-title">Connect credential</div>
        <div className="inline-fields">
          <select className="input" value={selectedProviderId} onChange={(event) => changeProvider(event.target.value)}>
            {providerList.map((provider) => (
              <option key={provider.provider_id} value={provider.provider_id}>
                {providerLabel(provider)}
              </option>
            ))}
          </select>
          <select className="input" value={selectedAppId} onChange={(event) => changeApp(event.target.value)}>
            {Object.values(selectedProvider?.connector_apps || {}).map((app) => (
              <option key={app.app_id} value={app.app_id}>
                {app.label || app.app_id}
              </option>
            ))}
          </select>
        </div>

        {capabilityIds.length ? (
          <div className="scope-list">
            {capabilityIds.map((capabilityId) => (
              <label className="scope-item" key={capabilityId}>
                <input
                  type="checkbox"
                  checked={selectedCapabilities.includes(capabilityId)}
                  onChange={() => toggleCapability(capabilityId)}
                  disabled={busy}
                />
                <span>{capabilityLabel(selectedProvider?.capabilities?.[capabilityId], capabilityId)}</span>
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
        <button className="btn" type="submit" disabled={busy || !selectedProviderId || !secretValue || selectedCapabilities.length === 0}>
          Connect
        </button>
      </form>
    </section>
  );
}
