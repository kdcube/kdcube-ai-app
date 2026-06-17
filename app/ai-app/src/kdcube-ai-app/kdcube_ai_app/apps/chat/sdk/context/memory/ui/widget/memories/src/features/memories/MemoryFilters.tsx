import { FormEvent } from 'react';
import { useAppDispatch, useAppSelector } from '../../app/hooks';
import {
  clearMemoryFocus,
  deleteMemoriesBySearch,
  exportMemories,
  focusMemories,
  loadMemories,
  loadMemoryEvents,
  normalizeMemoryRefs,
  setQuery,
  setStatus,
} from './memoriesSlice';

interface MemoryFiltersProps {
  maintenanceOpen?: boolean;
}

// A search string is treated as an ID lookup (not hybrid text search) when it
// carries any `mem:` / `me:` reference token — pasting one or many memory uris
// runs the same id-focus path the chat-open and pinboard-drop gestures use.
function looksLikeMemoryIds(text: string): boolean {
  return /(^|[\s,;])(mem|me):/i.test(text);
}

export function MemoryFilters({ maintenanceOpen = false }: MemoryFiltersProps) {
  const dispatch = useAppDispatch();
  const {
    focusedMemoryIds,
    memories,
    query,
    status,
    viewMode,
    loading,
  } = useAppSelector((state) => state.memories);
  const compact = viewMode === 'compact';
  const hasFilters = Boolean(query.trim() || status !== 'active');
  const focusedMemory = focusedMemoryIds.length === 1 ? memories.find((memory) => memory.id === focusedMemoryIds[0]) : undefined;
  const idMode = looksLikeMemoryIds(query);

  function submit(event: FormEvent) {
    event.preventDefault();
    const text = query.trim();
    if (looksLikeMemoryIds(text)) {
      const memoryIds = normalizeMemoryRefs(text);
      if (memoryIds.length) {
        // ID lookup — same focus path as chat-open / pinboard-drop. Clear the
        // hybrid query first (setQuery also resets focus), then set the focus.
        dispatch(setQuery(''));
        dispatch(focusMemories(memoryIds));
        void dispatch(loadMemories()).then(() => {
          void dispatch(loadMemoryEvents(memoryIds[0]));
        });
        return;
      }
    }
    void dispatch(loadMemories());
  }

  function downloadText(filename: string, content: string, mime = 'text/plain') {
    const blob = new Blob([content], { type: `${mime};charset=utf-8` });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  async function runExport(format: 'json' | 'markdown' | 'csv', all = false) {
    const payload = await dispatch(exportMemories({ format, all })).unwrap();
    if (!payload.ok || !payload.content) return;
    downloadText(payload.filename || `memories.${format}`, payload.content, payload.mime || 'text/plain');
  }

  async function runDelete(all = false) {
    const label = all ? 'all visible memory notes' : (hasFilters ? 'matching the current filters' : 'all active visible memory notes');
    if (!window.confirm(`Delete ${label}? This permanently deletes the notes and their memory events.`)) return;
    await dispatch(deleteMemoriesBySearch({ all })).unwrap();
    void dispatch(loadMemories());
  }

  return (
    <form className={`filters ${compact ? 'compact-filters' : ''}`} onSubmit={submit}>
      {focusedMemoryIds.length ? (
        <div className="focused-memory-filter">
          <div>
            <span>{focusedMemoryIds.length === 1 ? 'Filtered by memory id' : 'Filtered by memory ids'}</span>
            <strong>{focusedMemoryIds.length === 1 ? focusedMemory?.memory || focusedMemoryIds[0] : `${focusedMemoryIds.length} memories by id`}</strong>
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              dispatch(clearMemoryFocus());
              void dispatch(loadMemories());
            }}
          >
            Back to list
          </button>
        </div>
      ) : null}
      {/* One line: status filter + a single search box. Free text → hybrid
        * (semantic + lexical + recency); a value carrying mem: ids → id lookup. */}
      <div className="filter-bar">
        {compact ? null : (
          <select
            className="status-select"
            aria-label="Status"
            value={status}
            onChange={(event) => dispatch(setStatus(event.target.value))}
          >
            <option value="active">Active</option>
            <option value="weakened">Weakened</option>
            <option value="unsupported">Unsupported</option>
            <option value="retired">Retired</option>
            <option value="any">Any</option>
          </select>
        )}
        <div className="memory-search">
          <input
            value={query}
            onChange={(event) => dispatch(setQuery(event.target.value))}
            placeholder={compact ? 'Search memories…' : 'Search memories — or paste mem: ids'}
          />
          {query ? (
            <button
              type="button"
              className="memory-search-clear"
              title="Clear search"
              aria-label="Clear search"
              onClick={() => {
                dispatch(setQuery(''));
                void dispatch(loadMemories());
              }}
            >
              ×
            </button>
          ) : null}
          <button type="submit" className="memory-search-go" disabled={loading}>
            {idMode ? 'Show ids' : 'Search'}
          </button>
        </div>
      </div>
      {!compact && maintenanceOpen ? (
        <div className="memory-actions-row">
          <button type="button" className="secondary-button" disabled={loading} onClick={() => void runExport('json', false)}>
            Download matching JSON
          </button>
          <button type="button" className="secondary-button" disabled={loading} onClick={() => void runExport('json', true)}>
            Download all JSON
          </button>
          <button type="button" className="secondary-button" disabled={loading} onClick={() => void runExport('csv', false)}>
            CSV
          </button>
          <button type="button" className="danger-button" disabled={loading} onClick={() => void runDelete(false)}>
            {hasFilters ? 'Delete matching' : 'Delete active'}
          </button>
          <button type="button" className="danger-button" disabled={loading} onClick={() => void runDelete(true)}>
            Delete all
          </button>
        </div>
      ) : null}
    </form>
  );
}
