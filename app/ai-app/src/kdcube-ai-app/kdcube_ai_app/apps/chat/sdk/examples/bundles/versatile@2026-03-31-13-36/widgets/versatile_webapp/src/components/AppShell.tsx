import type { ReactNode } from 'react';
import { isTelegramWebApp } from '../telegram/utils';
import type { TabId } from '../store/types';

interface AppShellProps {
  activeTab: TabId;
  showAdmin: boolean;
  loading: boolean;
  error: string;
  onTabChange: (tab: TabId) => void;
  children: ReactNode;
}

export function AppShell({ activeTab, showAdmin, loading, error, onTabChange, children }: AppShellProps) {
  return (
    <main className="app">
      <header className="topbar">
        <div>
          <h1>Versatile</h1>
          <p>{isTelegramWebApp() ? 'Telegram WebApp' : 'KDCube widget'}</p>
        </div>
        <nav className="tabs" aria-label="Views">
          <button type="button" className={activeTab === 'memory' ? 'active' : ''} onClick={() => onTabChange('memory')}>Memory</button>
          <button type="button" className={activeTab === 'conversations' ? 'active' : ''} onClick={() => onTabChange('conversations')}>Chats</button>
          {showAdmin && (
            <button type="button" className={activeTab === 'telegram_admin' ? 'active' : ''} onClick={() => onTabChange('telegram_admin')}>Admin</button>
          )}
        </nav>
      </header>
      {error && <div className="error app-error">{error}</div>}
      {loading ? <div className="loading">Loading</div> : children}
    </main>
  );
}
