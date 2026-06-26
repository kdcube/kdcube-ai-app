import { useEffect, useState } from 'react';
import { callConnectionHubPublic } from '../store/apiClient';
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
  const [loading, setLoading] = useState(Boolean(challengeId));

  async function startTelegramFirstLink() {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const response = await callConnectionHubPublic<TelegramIdentityLinkResult>('telegram_identity_link_start', {});
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
    setResult(null);
    try {
      const response = await callConnectionHubPublic<TelegramIdentityLinkResult>('telegram_identity_link_complete', {
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

  useEffect(() => {
    if (!challengeId) {
      void startTelegramFirstLink();
      return undefined;
    }
    let cancelled = false;
    async function run() {
      setLoading(true);
      setError('');
      try {
        const response = await callConnectionHubPublic<TelegramIdentityLinkResult>('telegram_identity_link_complete', {
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

  return (
    <section className="link-card">
      <div className="link-badge">Connection Hub</div>
      <h1>Link Telegram</h1>
      <p className="muted">
        This Mini App proves your Telegram account. Open KDCube next to attach it to your platform user.
      </p>

      <div className="link-field">
        <span>Challenge</span>
        {challengeId || result?.challenge?.challenge_id ? (
          <code>{challengeId || result?.challenge?.challenge_id}</code>
        ) : (
          <input
            className="link-input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Paste challenge id"
          />
        )}
      </div>
      {!challengeId && (
        <button className="link-button" type="button" disabled={loading} onClick={() => void startTelegramFirstLink()}>
          Create Telegram proof
        </button>
      )}
      {!challengeId && result?.platform_claim_url && (
        <a className="link-button link-anchor" href={result.platform_claim_url} target="_blank" rel="noreferrer">
          Open KDCube to finish
        </a>
      )}
      {!challengeId && !result?.platform_claim_url && draft.trim() && (
        <button className="link-button secondary" type="button" disabled={loading} onClick={() => void complete()}>
          Complete pasted challenge
        </button>
      )}

      {loading && <div className="notice">{challengeId ? 'Completing link…' : 'Creating Telegram proof…'}</div>}
      {error && <div className="notice error">{error}</div>}
      {!loading && result?.ok && result.platform_claim_url && (
        <div className="notice success">
          Telegram account verified. Open KDCube and sign in there to finish linking this Telegram account.
        </div>
      )}
      {result?.ok && !result.platform_claim_url && (
        <div className="notice success">
          {result.link?.platform_user_id || result.challenge?.platform_user_id ? (
            <>
              Telegram account linked to platform user <code>{result.link?.platform_user_id || result.challenge?.platform_user_id}</code>.
            </>
          ) : (
            <>Telegram proof is ready for platform claim.</>
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
