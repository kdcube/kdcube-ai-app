import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAppDispatch, useAppSelector } from '../../app/hooks';
import {
  claimTelegramLinkChallenge,
  loadIdentityLinks,
  loadTelegramLinkChallengeStatus,
} from './identitySlice';
import { signOutPlatformSession, startPlatformSignIn } from '../../api/platformAuth';
import type { IdentityLink } from '../../api/types';

interface TelegramClaimPageProps {
  challengeId: string;
}

type ClaimStatus = 'checking' | 'confirm' | 'claiming' | 'connected' | 'signin_required' | 'failed';

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function isSignInRequired(error: string): boolean {
  const normalized = error.toLowerCase();
  return (
    normalized.includes('requires_authenticated_user') ||
    normalized.includes('require_authenticated_user') ||
    normalized.includes('login_required') ||
    normalized.includes('not authenticated') ||
    normalized.includes('unauthorized')
  );
}

async function startKdcubeSignIn() {
  const started = await startPlatformSignIn(window.location.href);
  if (!started) window.location.assign(`${window.location.origin}/platform/chat`);
}

export function TelegramClaimPage({ challengeId }: TelegramClaimPageProps) {
  const dispatch = useAppDispatch();
  const { telegramChallenge, links, platformUserId, error } = useAppSelector((s) => s.identity);
  const [status, setStatus] = useState<ClaimStatus>('checking');
  const [localError, setLocalError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [authBusy, setAuthBusy] = useState(false);

  const loadChallengeStatus = useCallback(async (isCancelled: () => boolean) => {
    setStatus('checking');
    setLocalError('');
    return dispatch(loadTelegramLinkChallengeStatus(challengeId)).unwrap()
      .then(async (result) => {
        if (isCancelled()) return;
        await dispatch(loadIdentityLinks()).unwrap().catch(() => undefined);
        if (isCancelled()) return;
        const challengeStatus = String(result.challenge?.status || '');
        setStatus(challengeStatus === 'completed' && result.link ? 'connected' : 'confirm');
      })
      .catch((err) => {
        if (isCancelled()) return;
        const text = errorText(err);
        setStatus(isSignInRequired(text) ? 'signin_required' : 'failed');
        setLocalError(text);
      });
  }, [challengeId, dispatch]);

  useEffect(() => {
    let cancelled = false;
    void loadChallengeStatus(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [attempt, loadChallengeStatus]);

  useEffect(() => {
    const onAuthChanged = (event: Event) => {
      const detail = (event as CustomEvent<{ authenticated?: boolean }>).detail;
      if (detail?.authenticated) setAttempt((value) => value + 1);
    };
    window.addEventListener('kdcube-auth-changed', onAuthChanged);
    return () => window.removeEventListener('kdcube-auth-changed', onAuthChanged);
  }, []);

  const link = useMemo<IdentityLink | null>(() => {
    const fromChallenge = telegramChallenge?.link;
    if (fromChallenge?.provider === 'telegram') return fromChallenge;
    const subject = telegramChallenge?.challenge?.provider_subject;
    if (subject) {
      return links.find((item) => item.provider === 'telegram' && item.provider_subject === subject) || null;
    }
    return links.find((item) => item.provider === 'telegram') || null;
  }, [links, telegramChallenge]);

  const displayName = link?.label || link?.provider_subject || telegramChallenge?.challenge?.label || 'Telegram';
  const telegramUserId = link?.provider_subject || telegramChallenge?.challenge?.provider_subject || '';
  const kdcubeUserId = (
    link?.platform_user_id
    || platformUserId
    || telegramChallenge?.platform_user_id
    || telegramChallenge?.challenge?.platform_user_id
    || ''
  );
  const message = localError || error;

  const claimLink = useCallback(async () => {
    setStatus('claiming');
    setLocalError('');
    try {
      await dispatch(claimTelegramLinkChallenge(challengeId)).unwrap();
      await dispatch(loadIdentityLinks()).unwrap().catch(() => undefined);
      setStatus('connected');
    } catch (err) {
      const text = errorText(err);
      setStatus(isSignInRequired(text) ? 'signin_required' : 'failed');
      setLocalError(text);
    }
  }, [challengeId, dispatch]);

  const clearPlatformSession = useCallback(async () => {
    setAuthBusy(true);
    try {
      await signOutPlatformSession();
      setStatus('signin_required');
      setLocalError('');
    } finally {
      setAuthBusy(false);
    }
  }, []);

  return (
    <div className="page claim-page">
      <section className="card claim-card">
        <span className="badge badge-ok">Connection Hub</span>
        <h1>Link Telegram to KDCube</h1>

        {status === 'checking' ? (
          <div className="notice">Checking KDCube sign-in and Telegram link details...</div>
        ) : null}

        {status === 'confirm' ? (
          <>
            <div className="notice">
              Confirm that you want to link this Telegram account to the KDCube
              account signed in in this browser.
            </div>
            <div className="account account-compact">
              <div>
                <div className="account-title">{displayName}</div>
                {telegramUserId ? <div className="account-sub">Telegram user id: {telegramUserId}</div> : null}
                {displayName && telegramUserId && displayName !== telegramUserId ? (
                  <div className="account-sub">Telegram nickname: {displayName}</div>
                ) : null}
                {kdcubeUserId ? <div className="account-sub">KDCube user id: {kdcubeUserId}</div> : null}
              </div>
            </div>
            <div className="button-row">
              <button type="button" className="btn" onClick={() => void claimLink()}>
                Link this Telegram account
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => void clearPlatformSession()}
                disabled={authBusy}
              >
                Sign out of KDCube
              </button>
            </div>
            <p className="muted">
              Use sign out if this is not the KDCube account you want to attach
              to Telegram.
            </p>
          </>
        ) : null}

        {status === 'claiming' ? (
          <div className="notice">Linking this Telegram account to KDCube...</div>
        ) : null}

        {status === 'connected' ? (
          <>
            <div className="notice success">
              Telegram is linked to your KDCube account.
            </div>
            <div className="account account-compact">
              <div>
                <div className="account-title">{displayName}</div>
                {telegramUserId ? <div className="account-sub">Telegram user id: {telegramUserId}</div> : null}
                {displayName && telegramUserId && displayName !== telegramUserId ? (
                  <div className="account-sub">Telegram nickname: {displayName}</div>
                ) : null}
                {kdcubeUserId ? <div className="account-sub">KDCube user id: {kdcubeUserId}</div> : null}
              </div>
            </div>
            <div className="button-row">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => void clearPlatformSession()}
                disabled={authBusy}
              >
                Sign out of KDCube
              </button>
            </div>
            <p className="muted">
              You can close this browser tab and return to Telegram. The Mini App
              will update the Connect tab.
            </p>
          </>
        ) : null}

        {status === 'signin_required' ? (
          <>
            <div className="notice">
              Sign in to KDCube in this browser to attach this Telegram account
              to your platform user.
            </div>
            <button type="button" className="btn" onClick={() => void startKdcubeSignIn()}>
              Sign in to KDCube
            </button>
            <p className="muted">
              This page uses KDCube platform sign-in from the runtime
              descriptor. After sign-in it will return here and retry the link.
            </p>
          </>
        ) : null}

        {status === 'failed' ? (
          <>
            <div className="error" role="alert">
              {message || 'Telegram connection did not finish.'}
            </div>
            <p className="muted">
              Return to Telegram and start the link again. If you are not signed
              into KDCube in this browser, sign in first and reopen the link.
            </p>
          </>
        ) : null}
      </section>
    </div>
  );
}
