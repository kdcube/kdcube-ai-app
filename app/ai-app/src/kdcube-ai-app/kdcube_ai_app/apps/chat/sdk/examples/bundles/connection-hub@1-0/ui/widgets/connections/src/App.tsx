import { useCallback, useEffect, useState } from 'react';
import { settings } from './api/settings';
import { useAppDispatch, useAppSelector } from './app/hooks';
import { AppShell, type ConnectionsTab } from './components/AppShell';
import { AuthenticatorsPanel } from './features/authenticators/AuthenticatorsPanel';
import { clearAuthenticatorsError, loadAuthenticators } from './features/authenticators/authenticatorsSlice';
import { ConnectionsList } from './features/connections/ConnectionsList';
import { clearConnectionsError, loadCatalog } from './features/connections/connectionsSlice';
import { IcloudPanel } from './features/email/IcloudPanel';
import { clearEmailError, loadEmailStatus } from './features/email/emailSlice';
import { ConnectionEdgesPanel } from './features/identity/ConnectionEdgesPanel';
import { clearIdentityError, loadConnectionEdges } from './features/identity/identitySlice';
import { TelegramClaimPage } from './features/identity/TelegramClaimPage';
import { TelegramMiniAppLinkPanel } from './features/identity/TelegramMiniAppLinkPanel';

function claimChallengeFromLocation(): string {
  const params = new URLSearchParams(window.location.search);
  return params.get('claim_challenge') || params.get('claimChallenge') || '';
}

function widgetModeFromLocation(): string {
  const params = new URLSearchParams(window.location.search);
  return (params.get('mode') || params.get('surface') || '').toLowerCase();
}

type TelegramConnectStatus = 'idle' | 'connecting' | 'connected' | 'failed';

function tabFromLocation(): ConnectionsTab {
  const params = new URLSearchParams(window.location.search);
  const value = (params.get('tab') || window.location.hash.replace(/^#/, '') || '').toLowerCase();
  if (value === 'accounts' || value === 'authenticators' || value === 'identity') return value;
  return 'identity';
}

export default function App() {
  const dispatch = useAppDispatch();
  const [claimChallengeId] = useState(claimChallengeFromLocation);
  const [widgetMode] = useState(widgetModeFromLocation);
  const telegramMiniAppMode = widgetMode === 'telegram-miniapp' || widgetMode === 'telegram_miniapp';
  const [runtimeReady, setRuntimeReady] = useState(false);
  const [activeTab, setActiveTab] = useState<ConnectionsTab>(tabFromLocation);
  const [telegramConnectStatus] = useState<TelegramConnectStatus>('idle');
  const connectionsLoading = useAppSelector((s) => s.connections.loading);
  const authenticatorsLoading = useAppSelector((s) => s.authenticators.loading);
  const emailLoading = useAppSelector((s) => s.email.loading);
  const identityLoading = useAppSelector((s) => s.identity.loading);
  const connectionsError = useAppSelector((s) => s.connections.error);
  const authenticatorsError = useAppSelector((s) => s.authenticators.error);
  const emailError = useAppSelector((s) => s.email.error);
  const identityError = useAppSelector((s) => s.identity.error);

  useEffect(() => {
    void settings.setupParentListener().then(async () => {
      setRuntimeReady(true);
      if (telegramMiniAppMode || claimChallengeId) return;
      void dispatch(loadConnectionEdges());
      void dispatch(loadAuthenticators());
      void dispatch(loadCatalog());
      void dispatch(loadEmailStatus());
    });
  }, [claimChallengeId, dispatch, telegramMiniAppMode]);

  const [refreshing, setRefreshing] = useState(false);
  const loading = identityLoading || authenticatorsLoading || connectionsLoading || emailLoading;
  const errors = [identityError, authenticatorsError, connectionsError, emailError].filter(Boolean) as string[];

  const dismissErrors = () => {
    dispatch(clearIdentityError());
    dispatch(clearAuthenticatorsError());
    dispatch(clearConnectionsError());
    dispatch(clearEmailError());
  };

  // Re-fetch the catalog + iCloud status (e.g. after finishing OAuth in the other
  // tab). Doesn't blank the page — just updates the lists.
  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await Promise.all([
        dispatch(loadConnectionEdges()).unwrap().catch(() => undefined),
        dispatch(loadAuthenticators()).unwrap().catch(() => undefined),
        dispatch(loadCatalog()).unwrap().catch(() => undefined),
        dispatch(loadEmailStatus()).unwrap().catch(() => undefined),
      ]);
    } finally {
      setRefreshing(false);
    }
  }, [dispatch]);

  const changeTab = useCallback((next: ConnectionsTab) => {
    setActiveTab(next);
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('tab', next);
      window.history.replaceState({}, '', url.toString());
    } catch {
      // Embedded/test contexts may not allow history mutation.
    }
  }, []);

  if (telegramMiniAppMode) {
    if (!runtimeReady) {
      return (
        <div className="page">
          <p className="muted">Loading…</p>
        </div>
      );
    }
    return <TelegramMiniAppLinkPanel />;
  }

  if (claimChallengeId) {
    if (!runtimeReady) {
      return (
        <div className="page">
          <p className="muted">Loading…</p>
        </div>
      );
    }
    return <TelegramClaimPage challengeId={claimChallengeId} />;
  }

  if (loading) {
    return (
      <div className="page">
        <h1>Integrations</h1>
        <p className="muted">Loading…</p>
      </div>
    );
  }

  return (
    <AppShell
      errors={errors}
      onDismissError={dismissErrors}
      onRefresh={refresh}
      refreshing={refreshing}
      activeTab={activeTab}
      onTabChange={changeTab}
      telegramConnectStatus={telegramConnectStatus}
    >
      {activeTab === 'identity' ? <ConnectionEdgesPanel telegramConnectStatus={telegramConnectStatus} /> : null}
      {activeTab === 'authenticators' ? <AuthenticatorsPanel /> : null}
      {activeTab === 'accounts' ? (
        <>
          <ConnectionsList />
          <IcloudPanel />
        </>
      ) : null}
    </AppShell>
  );
}
