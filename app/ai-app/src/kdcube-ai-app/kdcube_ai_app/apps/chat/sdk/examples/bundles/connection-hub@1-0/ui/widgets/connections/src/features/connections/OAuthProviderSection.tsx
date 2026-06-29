import { useEffect, useMemo, useState } from 'react';
import { useAppDispatch, useAppSelector } from '../../app/hooks';
import { AccountRow } from '../../components/AccountRow';
import type { CatalogEntry, ConnectionAccount, ConnectionApp } from '../../api/types';
import { disconnectConnection, loadCatalog, startOAuth } from './connectionsSlice';

function accountTitle(a: ConnectionAccount): string {
  return a.display_name || a.email || a.workspace || a.account_id;
}

function accountSub(a: ConnectionAccount): string | undefined {
  const bits = [a.workspace, a.email].filter(Boolean) as string[];
  const seen = bits.filter((b) => b && b !== a.display_name);
  return seen.length ? seen.join(' · ') : undefined;
}

// Renders any connections-catalog provider (google, slack, …): app picker
// (when more than one client app) + per-connect scope checkboxes + accounts.
export function OAuthProviderSection({ entry }: { entry: CatalogEntry }) {
  const dispatch = useAppDispatch();
  const busy = useAppSelector((s) => s.connections.busy);

  const apps = useMemo<ConnectionApp[]>(
    () => (entry.apps ?? []).filter((a) => a.enabled !== false),
    [entry],
  );
  const [appId, setAppId] = useState<string>('');
  const [scopes, setScopes] = useState<string[]>([]);

  const selectedApp = useMemo(
    () => apps.find((a) => a.app_id === appId) ?? apps[0],
    [apps, appId],
  );

  // Default the per-connect selection to the app's full scope ceiling; the user
  // can untick to request less consent.
  useEffect(() => {
    setScopes(selectedApp?.scopes ?? []);
  }, [selectedApp]);

  const toggleScope = (scope: string) =>
    setScopes((cur) => (cur.includes(scope) ? cur.filter((s) => s !== scope) : [...cur, scope]));

  const ceiling = selectedApp?.scopes ?? [];
  const accounts = entry.accounts ?? [];

  const connect = async () => {
    const chosenAppId = apps.length > 1 ? appId || apps[0]?.app_id : undefined;
    const subset = scopes.length && scopes.length < ceiling.length ? scopes : undefined;
    const url = await dispatch(startOAuth({ provider: entry.provider, appId: chosenAppId, scopes: subset })).unwrap().catch(() => undefined);
    if (url) window.open(url, '_blank', 'noopener');
    void dispatch(loadCatalog());
  };

  const disconnect = (accountId: string) => {
    void dispatch(disconnectConnection({ provider: entry.provider, accountId })).then(() => dispatch(loadCatalog()));
  };

  return (
    <section className="card">
      <div className="card-head">
        <h2>{entry.label || entry.provider}</h2>
        {apps.length > 0 ? (
          <div className="oauth-connect">
            {apps.length > 1 ? (
              <select
                className="input input-inline"
                value={appId || apps[0].app_id}
                onChange={(e) => setAppId(e.target.value)}
              >
                {apps.map((app) => (
                  <option key={app.app_id} value={app.app_id}>
                    {app.label || app.app_id}
                  </option>
                ))}
              </select>
            ) : null}
            <button className="btn" onClick={connect} disabled={busy}>
              Connect {entry.label || entry.provider}
            </button>
          </div>
        ) : null}
      </div>

      {apps.length > 0 && ceiling.length > 0 ? (
        <div className="scopes">
          <span className="muted small">
            Consent scopes for this connect (untick to request less):
          </span>
          <div className="scope-list">
            {ceiling.map((scope) => (
              <label key={scope} className="scope-item">
                <input
                  type="checkbox"
                  checked={scopes.includes(scope)}
                  onChange={() => toggleScope(scope)}
                  disabled={busy}
                />
                <code>{scope}</code>
              </label>
            ))}
          </div>
        </div>
      ) : null}

      {apps.length === 0 ? (
        <p className="muted">{entry.label || entry.provider} is not configured yet.</p>
      ) : accounts.length === 0 ? (
        <p className="muted">No {entry.label || entry.provider} accounts connected.</p>
      ) : (
        <ul className="accounts">
          {accounts.map((a) => (
            <AccountRow
              key={a.account_id}
              title={accountTitle(a)}
              subtitle={accountSub(a)}
              busy={busy}
              onDisconnect={() => disconnect(a.account_id)}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
