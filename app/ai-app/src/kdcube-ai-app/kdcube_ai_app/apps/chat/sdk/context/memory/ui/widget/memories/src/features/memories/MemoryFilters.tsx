import { FormEvent } from 'react';
import { useAppDispatch, useAppSelector } from '../../app/hooks';
import { loadMemories, setKeywordsFilter, setLabelsFilter, setQuery, setScopeFilter, setStatus } from './memoriesSlice';
import type { ScopeFilter } from '../../api/types';

export function MemoryFilters() {
  const dispatch = useAppDispatch();
  const {
    allowAllUserMemories,
    keywordsFilter,
    labelsFilter,
    query,
    scopeFilter,
    status,
    loading,
  } = useAppSelector((state) => state.memories);

  function submit(event: FormEvent) {
    event.preventDefault();
    void dispatch(loadMemories());
  }

  return (
    <form className="filters" onSubmit={submit}>
      <div className="filter-row">
        <label>
          <span>Scope</span>
          <select
            value={scopeFilter}
            onChange={(event) => {
              dispatch(setScopeFilter(event.target.value as ScopeFilter));
              void dispatch(loadMemories());
            }}
          >
            <option value="current_bundle">This bundle</option>
            {allowAllUserMemories ? <option value="all_user_memories">All user memories</option> : null}
          </select>
        </label>
        <label>
          <span>Status</span>
          <select value={status} onChange={(event) => dispatch(setStatus(event.target.value))}>
            <option value="active">Active</option>
            <option value="weakened">Weakened</option>
            <option value="unsupported">Unsupported</option>
            <option value="retired">Retired</option>
            <option value="any">Any</option>
          </select>
        </label>
      </div>
      <div className="search-row">
        <input
          value={query}
          onChange={(event) => dispatch(setQuery(event.target.value))}
          placeholder="Semantic search"
        />
        <input
          value={labelsFilter}
          onChange={(event) => dispatch(setLabelsFilter(event.target.value))}
          placeholder="Tags"
        />
        <input
          value={keywordsFilter}
          onChange={(event) => dispatch(setKeywordsFilter(event.target.value))}
          placeholder="Keywords"
        />
        <button type="submit" disabled={loading}>
          Search
        </button>
      </div>
    </form>
  );
}
