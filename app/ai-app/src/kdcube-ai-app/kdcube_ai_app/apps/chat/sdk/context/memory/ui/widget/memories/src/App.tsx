import { useEffect, useMemo, useState } from 'react';
import { AppShell } from './components/AppShell';
import { useAppDispatch, useAppSelector } from './app/hooks';
import { settings } from './api/settings';
import { MemoryDetail } from './features/memories/MemoryDetail';
import { MemoryEditor } from './features/memories/MemoryEditor';
import { MemoryFilters } from './features/memories/MemoryFilters';
import { MemoryList } from './features/memories/MemoryList';
import { ReconciliationPanel } from './features/memories/ReconciliationPanel';
import { clearTransientErrors, loadMemories, setViewMode, updateMemoryPreferences } from './features/memories/memoriesSlice';

function compactModeFromLocation(): boolean {
  const params = new URLSearchParams(window.location.search);
  const view = String(params.get('view') || params.get('mode') || '').trim().toLowerCase();
  const compact = String(params.get('compact') || '').trim().toLowerCase();
  return view === 'compact' || compact === '1' || compact === 'true' || compact === 'yes';
}

export default function App() {
  const dispatch = useAppDispatch();
  const {
    allowWrite,
    count,
    error,
    memories,
    memoryUseEnabled,
    mutationError,
    saving,
    selectedId,
  } = useAppSelector((state) => state.memories);
  const compact = useMemo(() => compactModeFromLocation(), []);
  const [editorMode, setEditorMode] = useState<'create' | 'edit' | ''>('');
  const selectedMemory = memories.find((memory) => memory.id === selectedId);

  useEffect(() => {
    dispatch(setViewMode(compact ? 'compact' : 'full'));
    void settings.setupParentListener().then(() => dispatch(loadMemories()));
  }, [compact, dispatch]);

  return (
    <AppShell
      allowWrite={allowWrite}
      count={count}
      memoryUseEnabled={memoryUseEnabled}
      saving={saving}
      compact={compact}
      onCreate={() => setEditorMode('create')}
      onToggleMemoryUse={() => {
        void dispatch(updateMemoryPreferences({ memoryEnabled: !memoryUseEnabled })).then(() => dispatch(loadMemories()));
      }}
    >
      {!memoryUseEnabled ? (
        <div className="warning-box">
          Memory use is off. Existing notes remain visible for review, export, or deletion.
        </div>
      ) : null}
      <MemoryFilters />
      {compact ? null : <ReconciliationPanel />}
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
      <div className={`workspace ${compact ? 'compact-workspace' : ''}`}>
        <MemoryList />
        {compact ? null : <div className="side-panel">
          {editorMode === 'create' ? (
            <MemoryEditor mode="create" onClose={() => setEditorMode('')} />
          ) : null}
          {editorMode === 'edit' && selectedMemory ? (
            <MemoryEditor mode="edit" memory={selectedMemory} onClose={() => setEditorMode('')} />
          ) : null}
          {!editorMode ? <MemoryDetail onEdit={() => setEditorMode('edit')} /> : null}
        </div>}
      </div>
    </AppShell>
  );
}
