import { useMemo, useState } from 'react';
import { useAppDispatch, useAppSelector } from '../../app/hooks';
import { AccountRow } from '../../components/AccountRow';
import { connectIcloud, disconnectEmail, loadEmailStatus } from './emailSlice';

// iCloud is app-password (no OAuth), so it stays on the email integration —
// Gmail moved to the connections framework (a google provider).
export function IcloudPanel() {
  const dispatch = useAppDispatch();
  const { accounts, busy } = useAppSelector((s) => s.email);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');

  const icloudAccounts = useMemo(
    () => accounts.filter((a) => a.provider === 'icloud'),
    [accounts],
  );

  const submit = async () => {
    await dispatch(connectIcloud({ email, appPassword: password, displayName: name })).unwrap().catch(() => undefined);
    setEmail('');
    setPassword('');
    setName('');
    void dispatch(loadEmailStatus());
  };

  const disconnect = (accountId: string) => {
    void dispatch(disconnectEmail(accountId)).then(() => dispatch(loadEmailStatus()));
  };

  return (
    <section className="card">
      <div className="card-head">
        <h2>iCloud</h2>
      </div>
      {icloudAccounts.length === 0 ? (
        <p className="muted">No iCloud accounts connected.</p>
      ) : (
        <ul className="accounts">
          {icloudAccounts.map((a) => (
            <AccountRow
              key={a.account_id}
              title={a.display_name || a.email || a.account_id}
              subtitle={a.email && a.email !== a.display_name ? a.email : undefined}
              busy={busy}
              onDisconnect={() => disconnect(a.account_id)}
            />
          ))}
        </ul>
      )}
      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault();
          if (!busy && email.trim() && password) void submit();
        }}
      >
        <div className="form-title">Connect with an app-specific password</div>
        <input
          className="input"
          type="email"
          placeholder="you@icloud.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="username"
        />
        <input
          className="input"
          type="password"
          placeholder="app-specific password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
        />
        <input
          className="input"
          type="text"
          placeholder="display name (optional)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button className="btn" type="submit" disabled={busy || !email.trim() || !password}>
          Connect iCloud
        </button>
      </form>
    </section>
  );
}
