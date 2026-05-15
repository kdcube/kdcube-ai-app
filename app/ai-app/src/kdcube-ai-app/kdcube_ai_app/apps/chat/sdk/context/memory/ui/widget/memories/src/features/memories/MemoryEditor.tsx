import { FormEvent, useEffect, useState } from 'react';
import { useAppDispatch, useAppSelector } from '../../app/hooks';
import type { MemoryDraft, MemoryEntry } from '../../api/types';
import { createMemory, loadMemoryEvents, updateMemory } from './memoriesSlice';

interface MemoryEditorProps {
  mode: 'create' | 'edit';
  memory?: MemoryEntry;
  onClose: () => void;
}

function draftFromMemory(memory?: MemoryEntry): MemoryDraft {
  return {
    memory: memory?.memory || '',
    context: memory?.context || '',
    kind: memory?.kind || 'fact',
    status: memory?.status || 'active',
    labels: (memory?.labels || []).join(', '),
    keywords: (memory?.keywords || []).join(', '),
    importance: memory?.importance_score || 0.7,
    pinned: Boolean(memory?.pinned),
  };
}

function splitTerms(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

interface TermFieldProps {
  label: string;
  helper?: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
}

function TermField({ label, helper, value, placeholder, onChange }: TermFieldProps) {
  const [pending, setPending] = useState('');
  const terms = splitTerms(value);

  function commit(raw = pending) {
    const additions = splitTerms(raw);
    if (additions.length === 0) return;
    const next = Array.from(new Set([...terms, ...additions]));
    onChange(next.join(', '));
    setPending('');
  }

  function remove(term: string) {
    onChange(terms.filter((item) => item !== term).join(', '));
  }

  return (
    <label className="term-field">
      <span>{label}</span>
      {helper ? <small className="field-hint">{helper}</small> : null}
      <div className="chip-editor">
        {terms.map((term) => (
          <button
            type="button"
            className="edit-chip"
            key={term}
            onClick={() => remove(term)}
            aria-label={`Remove ${term}`}
          >
            {term}<span aria-hidden="true">x</span>
          </button>
        ))}
        <input
          value={pending}
          onBlur={() => commit()}
          onChange={(event) => {
            const next = event.target.value;
            if (next.includes(',')) commit(next);
            else setPending(next);
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ',') {
              event.preventDefault();
              commit();
            }
            if (event.key === 'Backspace' && !pending && terms.length > 0) {
              remove(terms[terms.length - 1]);
            }
          }}
          placeholder={placeholder}
        />
      </div>
    </label>
  );
}

export function MemoryEditor({ mode, memory, onClose }: MemoryEditorProps) {
  const dispatch = useAppDispatch();
  const { saving } = useAppSelector((state) => state.memories);
  const [draft, setDraft] = useState<MemoryDraft>(() => draftFromMemory(memory));

  useEffect(() => {
    setDraft(draftFromMemory(memory));
  }, [memory]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!draft.memory.trim()) return;
    if (mode === 'edit' && memory) {
      const result = await dispatch(updateMemory({ id: memory.id, draft })).unwrap();
      if (result.ok) {
        void dispatch(loadMemoryEvents(memory.id));
        onClose();
      }
      return;
    }
    const result = await dispatch(createMemory(draft)).unwrap();
    if (result.ok) onClose();
  }

  function setField<K extends keyof MemoryDraft>(key: K, value: MemoryDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  return (
    <form className="memory-editor" onSubmit={submit}>
      <div className="editor-head">
        <div>
          <span className="eyebrow">{mode === 'edit' ? 'Refine note' : 'Add note'}</span>
          <h2>{mode === 'edit' ? 'Edit memory note' : 'New memory note'}</h2>
        </div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close">x</button>
      </div>

      <label>
        <span>Note</span>
        <small className="field-hint">
          Write the compact trigger first, then the rule. Do not leave the condition only in context.
        </small>
        <textarea
          value={draft.memory}
          onChange={(event) => setField('memory', event.target.value)}
          rows={3}
          required
          placeholder="For engineering explanations, start with the practical impact before implementation details."
        />
      </label>

      <label>
        <span>Context / reason</span>
        <small className="field-hint">
          Why this exists: provenance, motivation, examples. This is not the only place for the rule guard.
        </small>
        <textarea
          value={draft.context}
          onChange={(event) => setField('context', event.target.value)}
          rows={3}
          placeholder="Created because prior summaries buried the user-visible impact. Examples: debugging notes, code reviews, implementation recaps."
        />
      </label>

      <div className="editor-grid">
        <label>
          <span>Kind</span>
          <input value={draft.kind} onChange={(event) => setField('kind', event.target.value)} />
        </label>
        <label>
          <span>Status</span>
          <select value={draft.status} onChange={(event) => setField('status', event.target.value)}>
            <option value="active">Active</option>
            <option value="weakened">Weakened</option>
            <option value="unsupported">Unsupported</option>
            <option value="retired">Retired</option>
          </select>
        </label>
      </div>

      <TermField
        label="Tags"
        helper="Broad categories for grouping and filtering."
        value={draft.labels}
        placeholder="communication-style, technical-explanations"
        onChange={(value) => setField('labels', value)}
      />

      <TermField
        label="Keywords"
        helper="Concrete search triggers and synonyms likely to appear in future requests."
        value={draft.keywords}
        placeholder="impact, implementation, debugging"
        onChange={(value) => setField('keywords', value)}
      />

      <label className="range-field">
        <span>Importance <strong>{Math.round(draft.importance * 100)}%</strong></span>
        <small className="field-hint">
          Importance affects ranking. Pinning makes an active memory tier 1; otherwise tier is computed from evidence.
        </small>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={draft.importance}
          onChange={(event) => setField('importance', Number(event.target.value))}
        />
      </label>

      <label className="checkbox-field">
        <input
          type="checkbox"
          checked={draft.pinned}
          onChange={(event) => setField('pinned', event.target.checked)}
        />
        <span>
          Pin to tier 1
          <small className="field-hint">Use for memories that should reliably appear before computed tier 2/3 notes.</small>
        </span>
      </label>

      <div className="editor-actions">
        <button type="button" className="secondary-button" onClick={onClose}>Cancel</button>
        <button type="submit" disabled={saving || !draft.memory.trim()}>
          {saving ? 'Saving...' : 'Save'}
        </button>
      </div>
    </form>
  );
}
