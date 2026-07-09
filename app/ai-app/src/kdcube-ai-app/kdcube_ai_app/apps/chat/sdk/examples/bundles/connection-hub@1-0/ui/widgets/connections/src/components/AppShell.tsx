import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { TabGuide } from './TabGuide';

export type ConnectionsTab = 'identity' | 'delegatedToKdcube' | 'providerConnections' | 'delegatedAccess' | 'accessMap' | 'authenticators';

export interface AppShellProps {
  errors: string[];
  onDismissError: () => void;
  onRefresh: () => void;
  refreshing?: boolean;
  activeTab: ConnectionsTab;
  onTabChange: (tab: ConnectionsTab) => void;
  telegramConnectStatus?: 'idle' | 'connecting' | 'connected' | 'failed';
  // Authenticator configuration is operator surface; the tab renders only
  // for platform admins (the backend enforces it regardless).
  showAuthenticators?: boolean;
  children: ReactNode;
}

// Page chrome shared by every view: title + Refresh, the standing tip notice, and
// any transient error banners surfaced from the slices.
export function AppShell({
  errors,
  onDismissError,
  onRefresh,
  refreshing,
  activeTab,
  onTabChange,
  telegramConnectStatus = 'idle',
  showAuthenticators = true,
  children,
}: AppShellProps) {
  /* The tab strip is a single-line carousel at EVERY width — the six tabs
   * never wrap into a second row. The strip is honest about its own
   * overflow: an edge fade appears on exactly the side(s) with clipped
   * content (this scroll listener + ResizeObserver keep data-fade-left/
   * right current), and the active tab is always scrolled into view. When
   * the strip fully fits, both fade flags stay false and no fade shows. */
  const tabsRef = useRef<HTMLElement | null>(null);
  const [fade, setFade] = useState({ left: false, right: false });
  const updateFade = useCallback(() => {
    const el = tabsRef.current;
    if (!el) return;
    const left = el.scrollLeft > 1;
    const right = el.scrollLeft + el.clientWidth < el.scrollWidth - 1;
    setFade((prev) => (prev.left === left && prev.right === right ? prev : { left, right }));
  }, []);
  useEffect(() => {
    const el = tabsRef.current;
    if (!el) return;
    updateFade();
    el.addEventListener('scroll', updateFade, { passive: true });
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(updateFade);
    observer?.observe(el);
    return () => {
      el.removeEventListener('scroll', updateFade);
      observer?.disconnect();
    };
  }, [updateFade]);
  useEffect(() => {
    // Selection/mount keeps the active tab visible in the scrolling strip.
    tabsRef.current
      ?.querySelector('.tab.active')
      ?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [activeTab]);

  return (
    <div className="page page-viewport" data-tab={activeTab}>
      <div className="page-head">
        <div>
          <p className="eyebrow">Connection Hub</p>
          <h1>Connections</h1>
        </div>
        <button className="btn btn-ghost" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? 'Refreshing…' : '↻ Refresh'}
        </button>
      </div>
      <div
        className="tabs-wrap"
        data-fade-left={fade.left || undefined}
        data-fade-right={fade.right || undefined}
      >
      <nav className="tabs" aria-label="Connection Hub sections" ref={(el) => { tabsRef.current = el; }}>
        <button
          type="button"
          className={`tab ${activeTab === 'identity' ? 'active' : ''}`}
          onClick={() => onTabChange('identity')}
        >
          Identity
        </button>
        <button
          type="button"
          className={`tab ${activeTab === 'delegatedToKdcube' ? 'active' : ''}`}
          onClick={() => onTabChange('delegatedToKdcube')}
        >
          Delegated to KDCube
        </button>
        <button
          type="button"
          className={`tab ${activeTab === 'providerConnections' ? 'active' : ''}`}
          onClick={() => onTabChange('providerConnections')}
        >
          Provider connections
        </button>
        <button
          type="button"
          className={`tab ${activeTab === 'delegatedAccess' ? 'active' : ''}`}
          onClick={() => onTabChange('delegatedAccess')}
        >
          Delegated by KDCube
        </button>
        {showAuthenticators ? (
          <button
            type="button"
            className={`tab ${activeTab === 'accessMap' ? 'active' : ''}`}
            onClick={() => onTabChange('accessMap')}
          >
            Access map
          </button>
        ) : null}
        {showAuthenticators ? (
          <button
            type="button"
            className={`tab ${activeTab === 'authenticators' ? 'active' : ''}`}
            onClick={() => onTabChange('authenticators')}
          >
            Authenticators
          </button>
        ) : null}
      </nav>
      </div>
      <TabGuide tab={activeTab} />
      {telegramConnectStatus === 'connecting' && (
        <div className="notice">Connecting the Telegram account to your signed-in KDCube user…</div>
      )}
      {telegramConnectStatus === 'connected' && (
        <div className="notice success">Telegram account connected. You can close Telegram and continue in KDCube.</div>
      )}
      {telegramConnectStatus === 'failed' && (
        <div className="error" role="alert">
          Telegram connection did not finish. Reopen the Telegram Mini App and start the link again.
        </div>
      )}
      {errors.map((err, i) => (
        <div className="error" key={`${i}-${err}`} role="alert" onClick={onDismissError}>
          {err}
        </div>
      ))}
      {children}
    </div>
  );
}
