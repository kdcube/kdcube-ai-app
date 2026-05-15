import { useEffect, useState } from 'react';
import { AppShell } from './components/AppShell';
import { useAppDispatch, useAppSelector } from './app/hooks';
import { settings } from './api/settings';
import { MemoryDetail } from './features/memories/MemoryDetail';
import { MemoryEditor } from './features/memories/MemoryEditor';
import { MemoryFilters } from './features/memories/MemoryFilters';
import { MemoryList } from './features/memories/MemoryList';
import { ReconciliationPanel } from './features/memories/ReconciliationPanel';
import { loadMemories } from './features/memories/memoriesSlice';

export default function App() {
  const dispatch = useAppDispatch();
  const { allowWrite, error, memories, mutationError, selectedId } = useAppSelector((state) => state.memories);
  const [editorMode, setEditorMode] = useState<'create' | 'edit' | ''>('');
  const selectedMemory = memories.find((memory) => memory.id === selectedId);

  useEffect(() => {
    void settings.setupParentListener().then(() => dispatch(loadMemories()));
  }, [dispatch]);

  return (
    <AppShell allowWrite={allowWrite} onCreate={() => setEditorMode('create')}>
      <MemoryFilters />
      <ReconciliationPanel />
      {error && <div className="error-box">{error}</div>}
      {mutationError && <div className="error-box">{mutationError}</div>}
      <div className="workspace">
        <MemoryList />
        <div className="side-panel">
          {editorMode === 'create' ? (
            <MemoryEditor mode="create" onClose={() => setEditorMode('')} />
          ) : null}
          {editorMode === 'edit' && selectedMemory ? (
            <MemoryEditor mode="edit" memory={selectedMemory} onClose={() => setEditorMode('')} />
          ) : null}
          {!editorMode ? <MemoryDetail onEdit={() => setEditorMode('edit')} /> : null}
        </div>
      </div>
    </AppShell>
  );
}
