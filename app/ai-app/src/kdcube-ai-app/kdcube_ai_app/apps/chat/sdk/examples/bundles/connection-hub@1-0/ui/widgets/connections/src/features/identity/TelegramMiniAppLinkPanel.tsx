import { useCallback, useEffect, useState } from 'react';
import {
  getConnectionHubLiveSessionId,
  reconnectConnectionHubLiveChannel,
  subscribeConnectionHubEvents,
} from '../../api/dataBus';
import { postPublicOp } from '../../api/client';
import type { IdentityLink, IdentityLinkChallengeResult } from '../../api/types';

interface TelegramStatusResult extends IdentityLinkChallengeResult {
  provider?: string;
  provider_subject?: string;
  connection_id?: string;
  linked?: boolean;
}

function textError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function TelegramMiniAppLinkPanel() {
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState<TelegramStatusResult | null>(null);
  const [challenge, setChallenge] = useState<TelegramStatusResult | null>(null);
  const linked = Boolean(status?.linked || status?.link || challenge?.linked || challenge?.link);
  const link = (status?.link || challenge?.link || null) as IdentityLink | null;
  const platformUrl = challenge?.platform_claim_url || '';
  const telegramSubject = link?.provider_subject || status?.provider_subject || challenge?.provider_subject || '';
  const telegramLabel = link?.label || status?.provider_subject || 'Telegram';

  const refresh = useCallback(async () => {
    const result = await postPublicOp<TelegramStatusResult>('telegram_identity_link_status');
    if (result.ok === false) throw new Error(result.message || result.error || 'Telegram status failed');
    setStatus(result);
    if (result.linked || result.link) setChallenge(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    refresh()
      .catch((err) => {
        if (!cancelled) setError(textError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  useEffect(() => {
    return subscribeConnectionHubEvents((event) => {
      if (event.type !== 'connection_hub.identity.link_changed') return;
      const data = event.data || {};
      if (data.provider && data.provider !== 'telegram') return;
      void refresh()
        .then(() => reconnectConnectionHubLiveChannel())
        .catch((err) => setError(textError(err)));
    }, (err) => setError(err.message));
  }, [refresh]);

  const start = async () => {
    setBusy(true);
    setError('');
    try {
      const liveSessionId = await getConnectionHubLiveSessionId();
      const result = await postPublicOp<TelegramStatusResult>('telegram_identity_link_start', {
        live_event_session_id: liveSessionId,
      });
      if (result.ok === false) throw new Error(result.message || result.error || 'Telegram link failed');
      setChallenge(result);
      if (result.linked || result.link) {
        await refresh();
      } else if (result.platform_claim_url) {
        window.open(result.platform_claim_url, '_blank', 'noopener,noreferrer');
      }
    } catch (err) {
      setError(textError(err));
    } finally {
      setBusy(false);
    }
  };

  const unlink = async () => {
    setBusy(true);
    setError('');
    try {
      const result = await postPublicOp<TelegramStatusResult>('telegram_identity_link_remove');
      if (result.ok === false) throw new Error(result.message || result.error || 'Telegram unlink failed');
      setChallenge(null);
      await refresh();
    } catch (err) {
      setError(textError(err));
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="page telegram-link-page">
        <p className="muted">Checking Telegram link…</p>
      </div>
    );
  }

  return (
    <div className="page telegram-link-page">
      <section className="card">
        <span className="badge badge-ok">Connection Hub</span>
        <h1>Telegram account</h1>
        {linked ? (
          <>
            <p className="notice success">
              This Telegram account is linked to your KDCube user.
            </p>
            <div className="account account-compact">
              <div>
                <div className="account-title">{telegramLabel}</div>
                {telegramSubject ? <div className="account-sub">Telegram user id: {telegramSubject}</div> : null}
                {telegramLabel && telegramSubject && telegramLabel !== telegramSubject ? (
                  <div className="account-sub">Telegram nickname: {telegramLabel}</div>
                ) : null}
                <div className="account-sub">
                  {link?.platform_user_id ? `KDCube user id: ${link.platform_user_id}` : 'Linked KDCube user'}
                </div>
              </div>
              <button className="btn btn-ghost" type="button" disabled={busy} onClick={unlink}>
                Unlink
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="muted">
              Link this Telegram account to the KDCube account you use in the browser.
              After linking, KDCube can recognize the same person from Telegram.
            </p>
            <ol className="flow-steps flow-steps-numbered">
              <li className={challenge ? 'done' : 'active'}>
                <strong>1. Confirm this Telegram account</strong>
                <span>Press the button below from inside Telegram.</span>
              </li>
              <li className={challenge && !linked ? 'active' : ''}>
                <strong>2. Sign in to KDCube</strong>
                <span>The browser opens KDCube. Sign in and approve the link.</span>
              </li>
              <li className={linked ? 'done' : ''}>
                <strong>3. Return here</strong>
                <span>This panel updates when the browser finishes linking.</span>
              </li>
            </ol>
            <div className="telegram-link-actions">
              <button className="btn" type="button" disabled={busy} onClick={start}>
                {challenge ? 'Open KDCube to finish' : 'Link this Telegram account'}
              </button>
              {platformUrl ? (
                <a className="btn btn-link" href={platformUrl} target="_blank" rel="noreferrer">
                  Open KDCube
                </a>
              ) : null}
            </div>
          </>
        )}
        {error ? <div className="error" role="alert">{error}</div> : null}
      </section>
    </div>
  );
}
