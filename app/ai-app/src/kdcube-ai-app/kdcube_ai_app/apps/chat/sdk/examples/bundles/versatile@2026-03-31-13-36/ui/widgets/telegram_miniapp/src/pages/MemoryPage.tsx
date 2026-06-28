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

// Flip to false to silence the layout/handshake trace. Kept on so the
// maintainer can confirm the initial-view-sync fix from the Telegram desktop
// devtools console (or by opening the mini-app URL in a browser).
const DEBUG = true;

function frameHeight(frame: HTMLIFrameElement | null): number {
  return frame ? Math.round(frame.getBoundingClientRect().height) : -1;
}

function debugLog(frame: HTMLIFrameElement | null, event: string, extra?: Record<string, unknown>): void {
  if (!DEBUG) return;
  console.log('[memory-tab]', new Date().toISOString().slice(11, 23), event, {
    iframeHeight: frameHeight(frame),
    hasContentWindow: Boolean(frame?.contentWindow),
    ...extra,
  });
}

interface MemoryPageProps {
  memory?: MemoryPayload;
  reload?: () => Promise<void>;
}

export function MemoryPage(_props: MemoryPageProps) {
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [count, setCount] = useState<number | null>(null);
  // Keep `expanded` reachable inside the persistent message listener without
  // re-subscribing on every toggle (which would drop the listener mid-handshake).
  const expandedRef = useRef(expanded);
  expandedRef.current = expanded;
  // The widget's FIRST kdcube-memory-widget-status proves it has mounted and is
  // listening — the iframe `onLoad` fires earlier (document load), before the
  // React widget hydrates, so the set-view posted there can be dropped.
  const widgetReadyRef = useRef(false);

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
  // and on the widget's first status (see below) so the initial view always
  // lands after the widget is mounted and listening.
  const syncView = useCallback((view: 'compact' | 'expanded') => {
    debugLog(frameRef.current, 'post kdcube-set-view', { view });
    frameRef.current?.contentWindow?.postMessage({
      type: 'kdcube-set-view',
      widget: MEMORY_WIDGET_ALIAS,
      view,
    }, '*');
  }, []);

  // Force the widget to re-measure its layout. The widget recomputes its
  // compact/expanded shell height on a window `resize` (ResizeObserver +
  // resize listener); a same-value `kdcube-set-view` is a no-op for it, so when
  // the very first set-view was dropped (posted before the widget hydrated) the
  // shell can stay collapsed. Bumping the iframe height by 1px across two frames
  // fires a real resize inside the frame and settles the layout — the same
  // cross-frame jiggle the scene uses to wake the iframe — without a flash.
  const nudgeFrameLayout = useCallback(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const base = frame.style.height;
    const measured = Math.round(frame.getBoundingClientRect().height);
    if (!measured) return;
    frame.style.height = `${measured + 1}px`;
    window.requestAnimationFrame(() => {
      if (frameRef.current) frameRef.current.style.height = base;
    });
  }, []);

  useEffect(() => {
    debugLog(frameRef.current, 'mount', { expanded });
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        const firstStatus = !widgetReadyRef.current;
        debugLog(frameRef.current, 'recv kdcube-memory-widget-status', {
          count: next, compact: data.compact, firstStatus, expanded: expandedRef.current,
        });
        setCount(Number.isFinite(next) ? next : null);
        // First status = the widget has hydrated and its message listener is
        // live. The set-view posted on iframe onLoad could have been dropped
        // (fired before hydration), leaving the iframe at its un-synced default
        // — the collapsed thin line. Re-post the current view now so compact
        // applies without needing a manual expand/collapse toggle.
        if (firstStatus) {
          widgetReadyRef.current = true;
          syncView(expandedRef.current ? 'expanded' : 'compact');
          // The widget mounts compact from the URL params, so the re-posted
          // view may be a no-op for it; nudge a resize so its shell settles to
          // the iframe height instead of the collapsed initial line.
          nudgeFrameLayout();
        }
        return;
      }
      if (data.type === 'kdcube-widget-view') {
        debugLog(frameRef.current, 'recv kdcube-widget-view', { view: data.view, expanded: expandedRef.current });
        setExpanded(data.view === 'expanded');
      }
    }
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [syncView, nudgeFrameLayout]);

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
          onLoad={() => {
            debugLog(frameRef.current, 'iframe onLoad', { expanded });
            syncView(expanded ? 'expanded' : 'compact');
          }}
        />
      </div>
    </section>
  );
}
