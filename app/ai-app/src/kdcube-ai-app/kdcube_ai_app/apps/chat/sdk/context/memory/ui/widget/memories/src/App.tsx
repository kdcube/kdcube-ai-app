import { useEffect, useMemo, useState, type DragEvent } from 'react';

// ─── [debug:memories-layout] temporary diagnostics ─────────────────
// Flip to true to surface a live overlay of iframe/shell/workspace
// heights and the in-flight memories state. Used to root-cause the
// expanded-view sizing issues; left in the source (gated off) so the
// next time the layout misbehaves we can re-enable it from one line.
const DEBUG_LAYOUT = false;

function DebugOverlay({ info }: { info: Record<string, string | number> }) {
  if (!DEBUG_LAYOUT) return null;
  return (
    <div style={{
      position: 'fixed',
      top: 2,
      right: 2,
      zIndex: 99999,
      padding: '4px 6px',
      borderRadius: 4,
      background: 'rgba(0, 0, 0, 0.82)',
      color: '#ffe168',
      fontFamily: 'ui-monospace, Menlo, monospace',
      fontSize: 10,
      lineHeight: 1.35,
      pointerEvents: 'none',
      whiteSpace: 'pre',
      maxWidth: '50vw',
    }}>
      {Object.entries(info).map(([k, v]) => `${k}: ${v}`).join('\n')}
    </div>
  );
}
import { AppShell } from './components/AppShell';
import { useAppDispatch, useAppSelector } from './app/hooks';
import { settings } from './api/settings';
import { MemoryDetail } from './features/memories/MemoryDetail';
import { MemoryEditor } from './features/memories/MemoryEditor';
import { MemoryFilters } from './features/memories/MemoryFilters';
import { MemoryList } from './features/memories/MemoryList';
import { ReconciliationPanel } from './features/memories/ReconciliationPanel';
import {
  clearTransientErrors,
  focusMemories,
  loadMemories,
  loadMemoryEvents,
  normalizeMemoryRefs,
  setViewMode,
  updateMemoryPreferences,
} from './features/memories/memoriesSlice';

function compactModeFromLocation(): boolean {
  const params = new URLSearchParams(window.location.search);
  const view = String(params.get('view') || params.get('mode') || '').trim().toLowerCase();
  const compact = String(params.get('compact') || '').trim().toLowerCase();
  return view === 'compact' || compact === '1' || compact === 'true' || compact === 'yes';
}

function hostControlsFromLocation(): boolean {
  const params = new URLSearchParams(window.location.search);
  const value = String(params.get('host_controls') || params.get('hostControls') || '').trim().toLowerCase();
  return value === '1' || value === 'true' || value === 'yes';
}

function memRefsFromValue(value: unknown): string[] {
  if (!value || typeof value !== 'object') {
    if (typeof value === 'string' && value.trim().startsWith('mem:')) return [value.trim()];
    return [];
  }
  const raw = value as Record<string, unknown>;
  const data = raw.data && typeof raw.data === 'object' ? raw.data as Record<string, unknown> : {};
  const direct = [
    raw.object_ref,
    raw.ref,
    raw.logical_path,
    raw.logicalPath,
    raw.id,
    data.object_ref,
    data.memory_id,
  ].filter((item): item is string => typeof item === 'string' && item.trim());
  const refs = direct.flatMap((item) => item.trim().startsWith('mem:') ? [item.trim()] : []);
  const kind = String(raw.kind || raw.type || '').trim();
  const rawMemoryId = typeof data.memory_id === 'string' ? data.memory_id.trim() : '';
  if (kind.includes('memory') && rawMemoryId) refs.push(`mem:${normalizeMemoryRefs(rawMemoryId)[0] || rawMemoryId}`);
  return refs;
}

function memoryIdsFromPayload(value: unknown): string[] {
  if (!value || typeof value !== 'object') return [];
  const raw = value as Record<string, unknown>;
  const rawItems = Array.isArray(raw.contexts)
    ? raw.contexts
    : Array.isArray(raw.items)
      ? raw.items
      : Array.isArray(raw.cards)
        ? raw.cards
        : [raw.context, raw];
  return normalizeMemoryRefs(rawItems.flatMap(memRefsFromValue));
}

function memoryIdsFromDataTransfer(dataTransfer: DataTransfer): string[] {
  const candidates: string[] = [];
  const jsonTypes = ['application/vnd.kdcube.context+json', 'application/json'];
  jsonTypes.forEach((mimeType) => {
    const raw = dataTransfer.getData(mimeType);
    if (!raw) return;
    try {
      candidates.push(...memoryIdsFromPayload(JSON.parse(raw)));
    } catch {
      // Ignore non-JSON drag payloads for this MIME type.
    }
  });
  candidates.push(...normalizeMemoryRefs(dataTransfer.getData('text/uri-list')));
  return normalizeMemoryRefs(candidates);
}

export default function App() {
  const dispatch = useAppDispatch();
  const {
    allowWrite,
    count,
    error,
    focusedMemoryIds,
    loading,
    memories,
    memoryUseEnabled,
    mutationError,
    saving,
    selectedId,
    viewMode,
  } = useAppSelector((state) => state.memories);
  const [debugInfo, setDebugInfo] = useState<Record<string, string | number>>({});
  const initialCompact = useMemo(() => compactModeFromLocation(), []);
  const hostControls = useMemo(() => hostControlsFromLocation(), []);
  const [compact, setCompact] = useState(initialCompact);
  const [editorMode, setEditorMode] = useState<'create' | 'edit' | ''>('');
  const [maintenanceOpen, setMaintenanceOpen] = useState(false);
  const [dropActive, setDropActive] = useState(false);
  const selectedMemory = memories.find((memory) => memory.id === selectedId);
  // In expanded view we always show the side-panel when a focus filter
  // is active — the right column then carries MemoryDetail for the
  // dropped/opened memory so the bottom half of the widget is filled
  // with useful content instead of an empty grid below a single row.
  const hasFocus = focusedMemoryIds.length > 0;
  const showSidePanel = !compact && (editorMode === 'create' || editorMode === 'edit' || Boolean(selectedMemory) || hasFocus);

  function focusMemoryIdsKeepView(memoryIds: string[]) {
    // Used by the drop handler. The widget's current view (compact or full)
    // is preserved — drop is a focus/filter gesture, not a view switch. The
    // user can resize the pane separately if they want more room.
    const ids = normalizeMemoryRefs(memoryIds);
    if (!ids.length) return;
    setEditorMode('');
    dispatch(focusMemories(ids));
    void dispatch(loadMemories()).then(() => {
      void dispatch(loadMemoryEvents(ids[0]));
    });
  }

  function focusAndExpandMemoryIds(memoryIds: string[]) {
    // Used by the host 'open' message — an explicit request to open this
    // memory in the full editor layout.
    const ids = normalizeMemoryRefs(memoryIds);
    if (!ids.length) return;
    setCompact(false);
    setEditorMode('');
    dispatch(setViewMode('full'));
    dispatch(focusMemories(ids));
    void dispatch(loadMemories()).then(() => {
      void dispatch(loadMemoryEvents(ids[0]));
    });
  }

  useEffect(() => {
    dispatch(setViewMode(compact ? 'compact' : 'full'));
    void settings.setupParentListener().then(() => dispatch(loadMemories()));
  }, [compact, dispatch]);

  useEffect(() => {
    document.documentElement.dataset.memoryView = compact ? 'compact' : 'full';
    return () => {
      delete document.documentElement.dataset.memoryView;
    };
  }, [compact]);

  // [debug:memories-layout] Measure DOM sizes + state so we can see what
  // the iframe is actually rendering at instead of theorizing about CSS.
  useEffect(() => {
    if (!DEBUG_LAYOUT) return;
    const measure = () => {
      const root = document.getElementById('root');
      const shell = document.querySelector('.app-shell');
      const filters = document.querySelector('.filters');
      const workspace = document.querySelector('.workspace');
      const memoryList = document.querySelector('.memory-list');
      const sidePanel = document.querySelector('.side-panel');
      const measured: Record<string, string | number> = {
        win: `${window.innerWidth}x${window.innerHeight}`,
        html: document.documentElement.clientHeight,
        body: document.body.clientHeight,
        root: root ? (root as HTMLElement).offsetHeight : -1,
        shell: shell ? (shell as HTMLElement).offsetHeight : -1,
        filters: filters ? (filters as HTMLElement).offsetHeight : -1,
        workspace: workspace ? (workspace as HTMLElement).offsetHeight : -1,
        memList: memoryList ? (memoryList as HTMLElement).offsetHeight : -1,
        sidePnl: sidePanel ? (sidePanel as HTMLElement).offsetHeight : -1,
        compact: String(compact),
        viewMode,
        loading: String(loading),
        memCnt: memories.length,
        count,
        focused: focusedMemoryIds.length,
        selId: selectedId ? selectedId.slice(0, 10) : 'none',
      };
      console.log('[debug:memories-layout]', measured);
      setDebugInfo(measured);
    };
    // Defer to next animation frame so the browser has finished its
    // re-layout pass before we read element heights — otherwise the
    // window-resize event fires with new window.innerHeight values but
    // document.documentElement.clientHeight is still stale, and the
    // overlay shows `win` moving while every other field looks frozen.
    let pending = 0;
    const scheduleMeasure = () => {
      if (pending) return;
      pending = window.requestAnimationFrame(() => {
        pending = 0;
        measure();
      });
    };
    measure();
    const id = window.setTimeout(measure, 250);
    window.addEventListener('resize', scheduleMeasure);
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined' && document.documentElement) {
      ro = new ResizeObserver(scheduleMeasure);
      ro.observe(document.documentElement);
      if (document.body) ro.observe(document.body);
      const root = document.getElementById('root');
      if (root) ro.observe(root);
    }
    return () => {
      window.clearTimeout(id);
      if (pending) window.cancelAnimationFrame(pending);
      window.removeEventListener('resize', scheduleMeasure);
      if (ro) ro.disconnect();
    };
  }, [compact, viewMode, memories.length, count, focusedMemoryIds.length, selectedId, loading]);

  useEffect(() => {
    function onHostMessage(event: MessageEvent) {
      const data = event.data;
      if (!data || typeof data !== 'object') return;
      if (data.type === 'kdcube-set-view') {
        if (data.view === 'expanded') setCompact(false);
        if (data.view === 'compact') setCompact(true);
        return;
      }
      if (data.type !== 'kdcube-memory-widget-command' || data.widget !== 'memories') return;
      if (data.action === 'create') {
        setCompact(false);
        setEditorMode('create');
        return;
      }
      if (data.action === 'open') {
        const memoryIds = normalizeMemoryRefs([
          data.memory_id,
          data.object_ref,
          ...(Array.isArray(data.memory_ids) ? data.memory_ids : []),
          ...(Array.isArray(data.object_refs) ? data.object_refs : []),
        ]);
        focusAndExpandMemoryIds(memoryIds);
      }
    }
    window.addEventListener('message', onHostMessage);
    return () => window.removeEventListener('message', onHostMessage);
  }, [dispatch]);

  useEffect(() => {
    if (!window.parent || window.parent === window) return;
    window.parent.postMessage({
      type: 'kdcube-memory-widget-status',
      widget: 'memories',
      count,
      compact,
      memoryUseEnabled,
    }, '*');
  }, [compact, count, memoryUseEnabled]);

  const requestExpand = () => {
    if (window.parent && window.parent !== window) {
      window.parent.postMessage({ type: 'kdcube-widget-view', widget: 'memories', view: 'expanded' }, '*');
      return;
    }
    setCompact(false);
  };

  const toggleMemoryUse = () => {
    void dispatch(updateMemoryPreferences({ memoryEnabled: !memoryUseEnabled })).then(() => dispatch(loadMemories()));
  };

  function handleDragOver(event: DragEvent<HTMLElement>) {
    if (!Array.from(event.dataTransfer.types || []).some((type) => (
      type === 'application/vnd.kdcube.context+json' ||
      type === 'application/json' ||
      type === 'text/uri-list'
    ))) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
    setDropActive(true);
  }

  function handleDrop(event: DragEvent<HTMLElement>) {
    const memoryIds = memoryIdsFromDataTransfer(event.dataTransfer);
    setDropActive(false);
    if (!memoryIds.length) return;
    event.preventDefault();
    focusMemoryIdsKeepView(memoryIds);
  }

  return (
    <AppShell
      allowWrite={allowWrite}
      count={count}
      memoryUseEnabled={memoryUseEnabled}
      saving={saving}
      dropActive={dropActive}
      compact={compact}
      hostControls={hostControls}
      onCreate={() => setEditorMode('create')}
      onExpand={compact && !hostControls ? requestExpand : undefined}
      onToggleMemoryUse={toggleMemoryUse}
      onDragLeave={() => setDropActive(false)}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {compact ? (
        <label className="compact-memory-toggle">
          <input
            type="checkbox"
            checked={memoryUseEnabled}
            disabled={saving}
            onChange={toggleMemoryUse}
          />
          <span>Use my memory</span>
        </label>
      ) : null}
      {!memoryUseEnabled ? (
        <div className="warning-box">
          Memory use is off. Existing notes remain visible for review, export, or deletion.
        </div>
      ) : null}
      <MemoryFilters />
      {compact ? null : (
        <>
          <div className="maintenance-toggle-row">
            <button
              type="button"
              className="secondary-button"
              onClick={() => setMaintenanceOpen((open) => !open)}
            >
              {maintenanceOpen ? 'Hide maintenance' : 'Show maintenance'}
            </button>
          </div>
          {maintenanceOpen ? <ReconciliationPanel /> : null}
        </>
      )}
      {error ? (
        <div className="error-box dismissible-error">
          <span>{error}</span>
          <button type="button" onClick={() => dispatch(clearTransientErrors())}>Dismiss</button>
        </div>
      ) : null}
      {mutationError ? (
        <div className="error-box dismissible-error">
          <span>{mutationError}</span>
          <button type="button" onClick={() => dispatch(clearTransientErrors())}>Dismiss</button>
        </div>
      ) : null}
      <div className={`workspace ${compact ? 'compact-workspace' : ''} ${showSidePanel ? 'with-side-panel' : ''}`}>
        <MemoryList />
        {showSidePanel ? <div className="side-panel">
          {editorMode === 'create' ? (
            <MemoryEditor mode="create" onClose={() => setEditorMode('')} />
          ) : null}
          {editorMode === 'edit' && selectedMemory ? (
            <MemoryEditor mode="edit" memory={selectedMemory} onClose={() => setEditorMode('')} />
          ) : null}
          {!editorMode ? <MemoryDetail onEdit={() => setEditorMode('edit')} /> : null}
        </div> : null}
      </div>
      <DebugOverlay info={debugInfo} />
    </AppShell>
  );
}
