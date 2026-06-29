import { FormEvent, useState } from 'react';
import { useAppDispatch, useAppSelector } from '../../app/hooks';
import {
  clearTelegramLinkChallenge,
  createTelegramLinkChallenge,
  linkIdentity,
  loadIdentityLinks,
  removeIdentity,
} from './identitySlice';

const providerOptions = ['google', 'telegram', 'slack', 'bundle'];

interface IdentityLinksPanelProps {
  telegramConnectStatus?: 'idle' | 'connecting' | 'connected' | 'failed';
}

export function IdentityLinksPanel({ telegramConnectStatus = 'idle' }: IdentityLinksPanelProps) {
  const dispatch = useAppDispatch();
  const { platformUserId, links, telegramChallenge, busy } = useAppSelector((s) => s.identity);
  const [provider, setProvider] = useState(providerOptions[0]);
  const [subject, setSubject] = useState('');
  const [label, setLabel] = useState('');
  const challenge = telegramChallenge?.challenge;
  const challengePending = challenge?.status === 'pending';
  const telegramLinked = challenge?.status === 'completed' || telegramConnectStatus === 'connected';

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!provider.trim() || !subject.trim()) return;
    await dispatch(linkIdentity({ provider: provider.trim(), providerSubject: subject.trim(), label: label.trim() })).unwrap().catch(() => undefined);
    setSubject('');
    setLabel('');
    void dispatch(loadIdentityLinks());
  };

  const remove = async (providerValue: string, subjectValue: string) => {
    await dispatch(removeIdentity({ provider: providerValue, providerSubject: subjectValue })).unwrap().catch(() => undefined);
    void dispatch(loadIdentityLinks());
  };

  const startTelegramLink = async () => {
    await dispatch(createTelegramLinkChallenge()).unwrap().catch(() => undefined);
  };

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Identity links</h2>
          {platformUserId ? <p className="muted">Platform user: <code>{platformUserId}</code></p> : null}
        </div>
      </div>

      <p className="muted">
        Record external identities that can route to the same platform user.
        Use Telegram or another verified account so KDCube can recognize you
        from more than one place. Connected accounts below are for delegated access.
      </p>

      <div className="proof-link">
        <div>
          <div className="form-title">Connect Telegram</div>
          <p className="muted">
            Use this when you are signed into KDCube and want to attach your Telegram account.
          </p>
          <ol className="flow-steps">
            <li className={challenge ? 'done' : 'active'}>Start the Telegram connection here.</li>
            <li className={challengePending ? 'active' : telegramLinked ? 'done' : ''}>Open Telegram and confirm the account.</li>
            <li className={telegramLinked ? 'done' : ''}>Return here. KDCube will show it as connected.</li>
          </ol>
        </div>
        <button className="btn" type="button" disabled={busy || challengePending} onClick={startTelegramLink}>
          Start Telegram connection
        </button>
      </div>

      {telegramChallenge?.challenge && (
        <div className={`challenge ${telegramLinked ? 'challenge-ok' : ''}`}>
          <div className="challenge-row">
            <span>Status</span>
            <strong>{telegramLinked ? 'connected' : telegramChallenge.challenge.status}</strong>
          </div>
          <div className="challenge-row muted-row">
            <span>Link code</span>
            <code>{telegramChallenge.challenge.challenge_id}</code>
          </div>
          {telegramLinked ? (
            <p className="muted">Telegram is connected to this KDCube user.</p>
          ) : telegramChallenge.telegram_link_url ? (
            <a className="btn btn-link" href={telegramChallenge.telegram_link_url} target="_blank" rel="noreferrer">
              Open Telegram to confirm
            </a>
          ) : (
            <p className="muted">Telegram link is not configured. Use the link code only if KDCube asks for it.</p>
          )}
          {telegramLinked && (
            <button className="btn btn-ghost" type="button" onClick={() => dispatch(clearTelegramLinkChallenge())}>
              Dismiss
            </button>
          )}
        </div>
      )}

      {links.length ? (
        <ul className="accounts">
          {links.map((link) => (
            <li className="account" key={`${link.provider}:${link.provider_subject}`}>
              <div>
                <div className="account-title">
                  {link.label || link.provider_subject}
                  <span className="badge badge-ok">{link.provider}</span>
                </div>
                <div className="account-sub">{link.provider_subject}</div>
              </div>
              <button
                className="btn btn-ghost"
                disabled={busy}
                onClick={() => remove(link.provider, link.provider_subject)}
              >
                Unlink
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No external identities linked yet.</p>
      )}

      <form className="form" onSubmit={submit}>
        <div className="form-title">Add identity link</div>
        <div className="inline-fields">
          <select className="input input-inline" value={provider} onChange={(event) => setProvider(event.target.value)}>
            {providerOptions.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
          <input
            className="input"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            placeholder="provider subject, email, telegram id, external user id"
          />
        </div>
        <input
          className="input"
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          placeholder="optional display label"
        />
        <button className="btn" type="submit" disabled={busy || !subject.trim()}>
          Link identity
        </button>
      </form>
    </section>
  );
}
