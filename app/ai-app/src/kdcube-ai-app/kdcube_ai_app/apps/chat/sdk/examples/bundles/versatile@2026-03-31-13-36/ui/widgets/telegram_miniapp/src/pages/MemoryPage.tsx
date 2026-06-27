import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { settings } from '../store/settings';
import { installConfigHandshakeHost } from '../auth/configHandshakeHost';
import type { MemoryPayload } from '../store/types';

// Memory lives in the user-memories app. The Mini App loads it as a same-origin
// served-widget iframe (like the scene host does) — the whole tab IS the widget.
// The host answers the iframe's standard CONFIG_REQUEST with a CONFIG_RESPONSE
// that carries the host-owned auth proof (telegramInitData); the widget promotes
// it onto its own requests without knowing Telegram.
//
// View model mirrors the scene's memory panel: the iframe is served in COMPACT
// mode with host_controls=1, so the widget suppresses its own header chrome and
// the host renders the compact header (title · count, add, expand/collapse).
// Expand/collapse is driven host-side by posting `kdcube-set-view` to the
// widget — no iframe reload — exactly as the scene does (ui/scene/src/main.tsx
// `syncMemoryWidgetView` + the memory-pane expand button).
const MEMORY_WIDGET_BUNDLE_ID = 'user-memories@2026-06-26';
const MEMORY_WIDGET_ALIAS = 'memories';
const MEMORY_WIDGET_IDENTITY = 'MEMORIES_WIDGET';
// Compact shows a short list; expand reveals the rest. Match the scene's small
// preview count so the compact tab stays a glanceable summary.
const COMPACT_LIMIT = '4';

interface MemoryPageProps {
  memory?: MemoryPayload;
  reload?: () => Promise<void>;
}

export function MemoryPage(_props: MemoryPageProps) {
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [count, setCount] = useState<number | null>(null);

  const memoryWidgetSrc = useMemo(
    () => settings.widgetUrlForBundle(MEMORY_WIDGET_BUNDLE_ID, MEMORY_WIDGET_ALIAS, {
      view: 'compact',
      compact: '1',
      host_controls: '1',
      limit: COMPACT_LIMIT,
    }),
    [],
  );

  // Answer the memory iframe's standard CONFIG_REQUEST. Inside Telegram the
  // CONFIG_RESPONSE config also carries the host-owned authContext (telegram
  // initData). A kdcube-auth-changed nudge re-triggers the handshake if initData
  // lands after the frame mounts.
  useEffect(
    () => installConfigHandshakeHost(frameRef.current, {
      identity: MEMORY_WIDGET_IDENTITY,
      bundleId: MEMORY_WIDGET_BUNDLE_ID,
    }),
    [memoryWidgetSrc],
  );

  // Tell the widget which view to render (compact/expanded). Posting on every
  // change keeps the widget in sync; it also re-posts on the iframe `onLoad`
  // so a freshly (re)loaded frame picks up the current view.
  const syncView = useCallback((view: 'compact' | 'expanded') => {
    frameRef.current?.contentWindow?.postMessage({
      type: 'kdcube-set-view',
      widget: MEMORY_WIDGET_ALIAS,
      view,
    }, '*');
  }, []);

  useEffect(() => {
    syncView(expanded ? 'expanded' : 'compact');
  }, [expanded, syncView]);

  // The widget reports its record count + (with host_controls) view-change
  // requests from its own affordances. Reflect those host-side.
  useEffect(() => {
    function onMessage(event: MessageEvent) {
      const data = event.data;
      if (!data || typeof data !== 'object' || data.widget !== MEMORY_WIDGET_ALIAS) return;
      if (data.type === 'kdcube-memory-widget-status') {
        const next = Number(data.count);
        setCount(Number.isFinite(next) ? next : null);
        return;
      }
      if (data.type === 'kdcube-widget-view') {
        setExpanded(data.view === 'expanded');
      }
    }
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  return (
    <section className={`page page-wide memory-embed-page${expanded ? ' memory-expanded' : ''}`}>
      <header className="memory-pane-header">
        <span className="memory-pane-title">
          <strong>Memories</strong>
          {count !== null ? <small>{count} in scope</small> : null}
        </span>
        <div className="memory-pane-actions">
          <button
            type="button"
            className="ghost-button icon-only"
            onClick={() => setExpanded((value) => !value)}
            title={expanded ? 'Compact memories' : 'Enlarge memories'}
            aria-label={expanded ? 'Compact memories' : 'Enlarge memories'}
          >
            {expanded ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7" />
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M8 3H3v5M21 8V3h-5M16 21h5v-5M3 16v5h5" />
                <path d="M3 3l7 7M21 3l-7 7M21 21l-7-7M3 21l7-7" />
              </svg>
            )}
          </button>
        </div>
      </header>
      <div className="memory-widget-frame">
        <iframe
          ref={frameRef}
          src={memoryWidgetSrc}
          title="Memories"
          className="memory-widget-iframe"
          onLoad={() => syncView(expanded ? 'expanded' : 'compact')}
        />
      </div>
    </section>
  );
}
