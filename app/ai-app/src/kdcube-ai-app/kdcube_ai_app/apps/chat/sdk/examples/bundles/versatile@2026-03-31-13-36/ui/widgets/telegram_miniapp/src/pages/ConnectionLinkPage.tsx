import { useEffect, useState } from 'react';
import { callOperation } from '../store/apiClient';
import type { TelegramIdentityLinkResult } from '../store/types';

interface ConnectionLinkPageProps {
  challengeId?: string;
}

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export function ConnectionLinkPage({ challengeId }: ConnectionLinkPageProps) {
  const [draft, setDraft] = useState(challengeId || '');
  const [result, setResult] = useState<TelegramIdentityLinkResult | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(Boolean(challengeId));
  const telegramFirst = !challengeId;
  const link = result?.link;
  const linked = Boolean(link?.platform_user_id || result?.challenge?.platform_user_id);
  const readyForKdcube = telegramFirst && Boolean(result?.ok && result?.platform_claim_url);

  async function refreshLinkStatus(options: { silent?: boolean } = {}) {
    if (!options.silent) {
      setLoading(true);
      setError('');
    }
    try {
      const response = await callOperation<TelegramIdentityLinkResult>('telegram_identity_link_status', {});
      if (response?.ok === false) {
        if (!options.silent) setError(response.message || response.error || 'Telegram link status failed');
      } else {
        setResult((current) => {
          if (response.link?.platform_user_id) return response;
          return current?.platform_claim_url ? { ...current, ...response, platform_claim_url: current.platform_claim_url } : response;
        });
      }
    } catch (e) {
      if (!options.silent) setError(message(e));
    } finally {
      if (!options.silent) setLoading(false);
    }
  }

  async function startTelegramFirstLink() {
    setLoading(true);
    setError('');
    setNotice('');
    setResult(null);
    try {
      const response = await callOperation<TelegramIdentityLinkResult>('telegram_identity_link_start', {});
      if (response?.ok === false) {
        setError(response.message || response.error || 'Telegram link start failed');
      } else {
        setResult(response);
      }
    } catch (e) {
      setError(message(e));
    } finally {
      setLoading(false);
    }
  }

  async function complete(nextChallengeId = draft) {
    const value = String(nextChallengeId || '').trim();
    if (!value) {
      setError('Challenge id is required');
      return;
    }
    setLoading(true);
    setError('');
    setNotice('');
    setResult(null);
    try {
      const response = await callOperation<TelegramIdentityLinkResult>('telegram_identity_link_complete', {
        challenge_id: value,
      });
      if (response?.ok === false) {
        setError(response.message || response.error || 'Telegram link failed');
      } else {
        setResult(response);
      }
    } catch (e) {
      setError(message(e));
    } finally {
      setLoading(false);
    }
  }

  async function unlinkTelegram() {
    setLoading(true);
    setError('');
    setNotice('');
    try {
      const response = await callOperation<TelegramIdentityLinkResult>('telegram_identity_link_remove', {});
      if (response?.ok === false) {
        setError(response.message || response.error || 'Telegram unlink failed');
      } else {
        setResult({
          ok: true,
          provider: response.provider || 'telegram',
          provider_subject: response.provider_subject,
          linked: false,
          removed: response.removed,
        });
        setNotice(response.message || 'Telegram account is no longer linked.');
      }
    } catch (e) {
      setError(message(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!challengeId) {
      void refreshLinkStatus();
      return undefined;
    }
    let cancelled = false;
    async function run() {
      setLoading(true);
      setError('');
      try {
        const response = await callOperation<TelegramIdentityLinkResult>('telegram_identity_link_complete', {
          challenge_id: challengeId,
        });
        if (cancelled) return;
        if (response?.ok === false) {
          setError(response.message || response.error || 'Telegram link failed');
        } else {
          setResult(response);
        }
      } catch (e) {
        if (!cancelled) setError(message(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void run();
    return () => {
      cancelled = true;
    };
  }, [challengeId]);

  useEffect(() => {
    if (!readyForKdcube || linked) return undefined;
    const refresh = () => void refreshLinkStatus({ silent: true });
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, [readyForKdcube, linked]);

  if (linked) {
    return (
      <section className="link-card">
        <div className="link-badge">Connection Hub</div>
        <h1>Telegram is linked</h1>
        <p className="muted">
          This Telegram account is attached to your KDCube identity. Requests from this Mini App can now be resolved through that platform account.
        </p>
        <div className="link-status-card done">
          <strong>Connected account</strong>
          <span>Telegram is linked to KDCube user <code>{link?.platform_user_id || result?.challenge?.platform_user_id}</code>.</span>
        </div>
        <div className="link-field">
          <span>Telegram</span>
          <code>{link?.label || result?.provider_subject || link?.provider_subject || 'current account'}</code>
        </div>
        <div className="link-field">
          <span>KDCube user</span>
          <code>{link?.platform_user_id || result?.challenge?.platform_user_id}</code>
        </div>
        <button className="link-button danger-button" type="button" disabled={loading} onClick={() => void unlinkTelegram()}>
          Unlink Telegram account
        </button>
        {loading && <div className="notice">Updating link…</div>}
        {error && <div className="notice error">{error}</div>}
      </section>
    );
  }

  return (
    <section className="link-card">
      <div className="link-badge">Connection Hub</div>
      <h1>Link Telegram</h1>
      <p className="muted">
        {telegramFirst
          ? 'Attach this Telegram account to the KDCube account you use in the browser.'
          : 'KDCube opened Telegram so you can confirm which Telegram account should be linked.'}
      </p>

      <ol className="link-steps">
        <li className={result?.ok ? 'done' : 'active'}>
          <strong>1. Create a Telegram proof</strong>
          <span>Telegram signs the account currently open in this Mini App.</span>
        </li>
        <li className={linked ? 'done' : readyForKdcube ? 'active' : ''}>
          <strong>2. Open KDCube and sign in</strong>
          <span>KDCube will show the browser account that will receive this Telegram link.</span>
        </li>
        <li className={linked ? 'done' : ''}>
          <strong>3. Approve the link in KDCube</strong>
          <span>When you return here, this tab will show the linked KDCube account.</span>
        </li>
      </ol>

      {(challengeId || result?.challenge?.challenge_id || draft.trim()) && !readyForKdcube && (
        <div className="link-field">
          <span>Link code</span>
          {challengeId || result?.challenge?.challenge_id ? (
            <code>{challengeId || result?.challenge?.challenge_id}</code>
          ) : (
            <input
              className="link-input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Paste link code"
            />
          )}
        </div>
      )}

      {telegramFirst && !result?.ok && (
        <button className="link-button" type="button" disabled={loading} onClick={() => void startTelegramFirstLink()}>
          Link this Telegram account
        </button>
      )}
      {readyForKdcube && (
        <a className="link-button link-anchor" href={result.platform_claim_url} target="_blank" rel="noreferrer">
          Open KDCube to approve
        </a>
      )}
      {telegramFirst && !result?.platform_claim_url && draft.trim() && (
        <button className="link-button secondary" type="button" disabled={loading} onClick={() => void complete()}>
          Complete pasted KDCube link code
        </button>
      )}

      {loading && <div className="notice">{challengeId ? 'Connecting this Telegram account…' : 'Checking Telegram link…'}</div>}
      {error && <div className="notice error">{error}</div>}
      {notice && <div className="notice success">{notice}</div>}
      {!loading && readyForKdcube && (
        <div className="notice success">
          Telegram proof is ready. Tap “Open KDCube to approve”, sign in there, and approve this Telegram link.
        </div>
      )}
      {result?.ok && !result.platform_claim_url && (
        <div className="notice success">
          {result.link?.platform_user_id || result.challenge?.platform_user_id ? (
            <>
              Connected. This Telegram account is linked to KDCube user <code>{result.link?.platform_user_id || result.challenge?.platform_user_id}</code>.
            </>
          ) : (
            <>Telegram is not linked yet. Use the button above to start linking it to your KDCube account.</>
          )}
        </div>
      )}
      {result?.link && (
        <div className="link-field">
          <span>Telegram</span>
          <code>{result.link.provider_subject}</code>
        </div>
      )}
    </section>
  );
}
