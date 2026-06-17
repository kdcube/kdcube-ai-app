import { useEffect, useRef, type DragEventHandler, type ReactNode } from 'react';

interface AppShellProps {
  children: ReactNode;
  allowWrite: boolean;
  count: number;
  memoryUseEnabled: boolean;
  onCreate: () => void;
  onExpand?: () => void;
  onToggleMemoryUse: () => void;
  onDragLeave?: DragEventHandler<HTMLElement>;
  onDragOver?: DragEventHandler<HTMLElement>;
  onDrop?: DragEventHandler<HTMLElement>;
  compact?: boolean;
  dropActive?: boolean;
  hostControls?: boolean;
  saving?: boolean;
  maintenanceOpen?: boolean;
  onToggleMaintenance?: () => void;
}

function notifyHostWidgetFocus(): void {
  try {
    if (typeof window === 'undefined' || window.parent === window) return;
    window.parent.postMessage({ type: 'kdcube-widget-focus', widget: 'memories' }, '*');
  } catch {
    // Focus promotion is a host-scene affordance only.
  }
}

export function AppShell({
  allowWrite,
  children,
  count,
  memoryUseEnabled,
  onCreate,
  onDragLeave,
  onDragOver,
  onDrop,
  onExpand,
  onToggleMemoryUse,
  compact = false,
  dropActive = false,
  hostControls = false,
  saving = false,
  maintenanceOpen = false,
  onToggleMaintenance,
}: AppShellProps) {
  const shellRef = useRef<HTMLElement | null>(null);

  // Report the actual rendered content height to the host so a floating
  // panel can fit to content (no empty space below a short compact list).
  // Measuring the lowest child bottom works even when the shell is stretched
  // to fill the iframe (scrollHeight would just return the iframe height).
  useEffect(() => {
    const el = shellRef.current;
    if (!el || typeof window === 'undefined' || window.parent === window) return;
    let raf = 0;
    const measure = () => {
      raf = 0;
      const top = el.getBoundingClientRect().top;
      let bottom = top;
      Array.from(el.children).forEach((child) => {
        const r = (child as HTMLElement).getBoundingClientRect();
        if (r.bottom > bottom) bottom = r.bottom;
      });
      const height = Math.max(0, Math.ceil(bottom - top) + 8);
      window.parent.postMessage({ type: 'kdcube-memory-resize', widget: 'memories', height, compact: Boolean(compact) }, '*');
    };
    const schedule = () => { if (!raf) raf = window.requestAnimationFrame(measure); };
    const ro = new ResizeObserver(schedule);
    ro.observe(el);
    const mo = new MutationObserver(schedule);
    mo.observe(el, { childList: true, subtree: true });
    schedule();
    return () => { ro.disconnect(); mo.disconnect(); if (raf) window.cancelAnimationFrame(raf); };
  }, [compact, count]);

  return (
    <main
      ref={shellRef}
      className={`app-shell ${compact ? 'compact-shell' : 'expanded-shell'} ${compact && hostControls ? 'host-controlled-shell' : ''} ${dropActive ? 'memory-drop-active' : ''}`}
      onDragLeave={onDragLeave}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onPointerDownCapture={notifyHostWidgetFocus}
    >
      {compact && hostControls ? null : <header className="app-header">
        <div className="app-title-block">
          {compact ? null : <h1>Memory notes</h1>}
          <p>{compact ? `${count} in scope` : `${count} records in scope`}</p>
        </div>
        <div className="app-header-actions">
          <label className={`memory-use-toggle ${compact ? 'sr-only' : ''}`}>
            <input
              type="checkbox"
              checked={memoryUseEnabled}
              onChange={onToggleMemoryUse}
              disabled={saving}
            />
            <span>Use my memory</span>
          </label>
          {allowWrite && !compact ? (
            <button type="button" className="primary-button" onClick={onCreate}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6 }}>
                <path d="M12 5v14M5 12h14" />
              </svg>
              New note
            </button>
          ) : null}
          {!compact && onToggleMaintenance ? (
            <button type="button" className="secondary-button header-maintenance-button" onClick={onToggleMaintenance}>
              {maintenanceOpen ? 'Hide maintenance' : 'Show maintenance'}
            </button>
          ) : null}
          {allowWrite && compact ? (
            <button
              type="button"
              className="icon-button compact-add-button"
              onClick={onCreate}
              aria-label="Add memory"
              title="Add memory"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
          ) : null}
          {compact && onExpand ? (
            <button
              type="button"
              className="icon-button compact-expand-button"
              onClick={onExpand}
              aria-label="Expand memories"
              title="Expand memories"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M8 3H3v5M16 3h5v5M21 16v5h-5M3 16v5h5" />
                <path d="M3 3l7 7M21 3l-7 7M21 21l-7-7M3 21l7-7" />
              </svg>
            </button>
          ) : null}
        </div>
      </header>}
      {children}
    </main>
  );
}
