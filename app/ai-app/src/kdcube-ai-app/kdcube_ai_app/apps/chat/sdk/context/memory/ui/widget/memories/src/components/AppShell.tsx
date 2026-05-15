import type { ReactNode } from 'react';

interface AppShellProps {
  children: ReactNode;
  allowWrite: boolean;
  onCreate: () => void;
}

export function AppShell({ allowWrite, children, onCreate }: AppShellProps) {
  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <span className="eyebrow">User memory</span>
          <h1>Memory Notes</h1>
          <p>Curated notes for this bundle.</p>
        </div>
        {allowWrite ? <button type="button" className="primary-button" onClick={onCreate}>New Note</button> : null}
      </header>
      {children}
    </main>
  );
}
