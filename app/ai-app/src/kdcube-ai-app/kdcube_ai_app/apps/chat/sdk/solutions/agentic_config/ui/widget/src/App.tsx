/**
 * Agent-instructions authoring widget.
 *
 * Stored instruction sets are ordered token lists in the composer vocabulary,
 * saved as IMMUTABLE versions under a slug id and wired to agents by ref
 * (`instr:custom:<id>[:<version>]`). This editor lists them, edits an item
 * list (palette tokens or literal text), previews the composed body exactly
 * as the runtime builds it, and saves the next version. Writes are admin
 * operations — the server refuses non-admin saves; this UI just shows the
 * denial honestly.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  getInstruction,
  listInstructions,
  previewBody,
  retireInstruction,
  saveVersion,
  type InstructionRecord,
} from './api.ts'
import { PALETTE } from './palette.ts'
import { settings } from './settings.ts'

type Notice = { kind: 'success' | 'error'; text: string } | null

interface Draft {
  instruction_id: string
  name: string
  description: string
  items: string[]
  /** the loaded record when editing an existing set (null = new) */
  loaded: InstructionRecord | null
}

const EMPTY_DRAFT: Draft = { instruction_id: '', name: '', description: '', items: [''], loaded: null }

export default function App() {
  const [ready, setReady] = useState(false)
  const [authNonce, setAuthNonce] = useState(0)

  useEffect(() => {
    let alive = true
    void settings.setupParentListener().then(() => {
      if (alive) setReady(true)
    })
    const onAuthChanged = () => {
      void settings.requestConfig().then(() => {
        if (alive) setAuthNonce((n) => n + 1)
      })
    }
    window.addEventListener('kdcube-auth-changed', onAuthChanged as EventListener)
    return () => {
      alive = false
      window.removeEventListener('kdcube-auth-changed', onAuthChanged as EventListener)
    }
  }, [])

  if (!ready) return <div className="agc-boot">Loading…</div>
  return <Editor key={authNonce} />
}

function Editor() {
  const [rows, setRows] = useState<InstructionRecord[]>([])
  const [includeRetired, setIncludeRetired] = useState(false)
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT)
  const [preview, setPreview] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<Notice>(null)

  const refresh = useCallback(async (retired: boolean) => {
    try {
      setRows(await listInstructions(retired))
    } catch (err) {
      setNotice({ kind: 'error', text: err instanceof Error ? err.message : String(err) })
    }
  }, [])

  useEffect(() => {
    void refresh(includeRetired)
  }, [refresh, includeRetired])

  const open = async (ref: string) => {
    setBusy(true)
    setNotice(null)
    setPreview(null)
    try {
      const record = await getInstruction(ref)
      setDraft({
        instruction_id: record.instruction_id,
        name: record.name,
        description: record.description,
        items: record.items.length ? [...record.items] : [''],
        loaded: record,
      })
    } catch (err) {
      setNotice({ kind: 'error', text: err instanceof Error ? err.message : String(err) })
    } finally {
      setBusy(false)
    }
  }

  const cleanItems = () => draft.items.map((v) => v.trim()).filter(Boolean)

  const runPreview = async () => {
    setBusy(true)
    setNotice(null)
    try {
      const result = await previewBody(cleanItems())
      setPreview(result.body)
    } catch (err) {
      setNotice({ kind: 'error', text: err instanceof Error ? err.message : String(err) })
    } finally {
      setBusy(false)
    }
  }

  const save = async () => {
    setBusy(true)
    setNotice(null)
    try {
      const record = await saveVersion({
        instruction_id: draft.instruction_id.trim().toLowerCase(),
        name: draft.name.trim(),
        description: draft.description.trim(),
        items: cleanItems(),
      })
      setNotice({ kind: 'success', text: `Saved ${record.ref} (by ${record.created_by})` })
      setDraft((d) => ({ ...d, loaded: record }))
      void refresh(includeRetired)
    } catch (err) {
      setNotice({ kind: 'error', text: err instanceof Error ? err.message : String(err) })
    } finally {
      setBusy(false)
    }
  }

  const retire = async (ref: string) => {
    setBusy(true)
    setNotice(null)
    try {
      await retireInstruction(ref)
      setNotice({ kind: 'success', text: `Retired ${ref}` })
      void refresh(includeRetired)
      if (draft.loaded) void open(`instr:custom:${draft.loaded.instruction_id}:${draft.loaded.version}`)
    } catch (err) {
      setNotice({ kind: 'error', text: err instanceof Error ? err.message : String(err) })
    } finally {
      setBusy(false)
    }
  }

  const setItem = (index: number, value: string) =>
    setDraft((d) => ({ ...d, items: d.items.map((v, i) => (i === index ? value : v)) }))
  const removeItem = (index: number) =>
    setDraft((d) => ({ ...d, items: d.items.filter((_, i) => i !== index) }))
  const moveItem = (index: number, delta: number) =>
    setDraft((d) => {
      const next = [...d.items]
      const target = index + delta
      if (target < 0 || target >= next.length) return d
      ;[next[index], next[target]] = [next[target], next[index]]
      return { ...d, items: next }
    })
  const appendItem = (value: string) =>
    setDraft((d) => ({ ...d, items: [...d.items.filter((v, i) => v.trim() || i < d.items.length - 1), value] }))

  return (
    <div className="agc-root">
      <aside className="agc-side">
        <div className="agc-side-head">
          <h2>Instruction sets</h2>
          <button className="agc-btn" onClick={() => { setDraft(EMPTY_DRAFT); setPreview(null); setNotice(null) }}>
            New
          </button>
        </div>
        <label className="agc-check">
          <input
            type="checkbox"
            checked={includeRetired}
            onChange={(e) => setIncludeRetired(e.target.checked)}
          />
          include retired
        </label>
        <div className="agc-list">
          {rows.map((row) => (
            <button
              key={row.instruction_id}
              className={
                'agc-list-row' + (draft.loaded?.instruction_id === row.instruction_id ? ' is-active' : '')
              }
              onClick={() => void open(row.ref)}
            >
              <span className="agc-list-name">{row.name}</span>
              <span className="agc-list-ref">{row.ref}</span>
              {row.status !== 'active' ? <span className="agc-tag agc-tag-warn">{row.status}</span> : null}
            </button>
          ))}
          {!rows.length ? <div className="agc-empty">No stored instruction sets yet.</div> : null}
        </div>
      </aside>

      <main className="agc-main">
        {notice ? <div className={`agc-notice agc-notice-${notice.kind}`}>{notice.text}</div> : null}

        <div className="agc-field-row">
          <label className="agc-field">
            <span>Id (slug)</span>
            <input
              value={draft.instruction_id}
              disabled={Boolean(draft.loaded)}
              placeholder="support-tone"
              onChange={(e) => setDraft((d) => ({ ...d, instruction_id: e.target.value }))}
            />
          </label>
          <label className="agc-field">
            <span>Name</span>
            <input
              value={draft.name}
              placeholder="Support tone"
              onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
            />
          </label>
        </div>
        <label className="agc-field">
          <span>Description</span>
          <input
            value={draft.description}
            onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))}
          />
        </label>

        <div className="agc-items-head">
          <h3>Items (composed in order)</h3>
          <select
            className="agc-palette"
            value=""
            onChange={(e) => {
              if (e.target.value) appendItem(e.target.value)
              e.target.value = ''
            }}
          >
            <option value="">Add from palette…</option>
            {PALETTE.map((group) => (
              <optgroup key={group.label} label={group.label}>
                {group.tokens.map((token) => (
                  <option key={token} value={token}>{token}</option>
                ))}
              </optgroup>
            ))}
          </select>
          <button className="agc-btn" onClick={() => appendItem('')}>Add literal text</button>
        </div>
        <div className="agc-items">
          {draft.items.map((item, index) => (
            <div key={index} className="agc-item">
              <textarea
                rows={item.includes('\n') || item.length > 80 ? 4 : 1}
                value={item}
                placeholder="token or literal instruction text"
                onChange={(e) => setItem(index, e.target.value)}
              />
              <div className="agc-item-actions">
                <button title="Move up" onClick={() => moveItem(index, -1)}>↑</button>
                <button title="Move down" onClick={() => moveItem(index, 1)}>↓</button>
                <button title="Remove" onClick={() => removeItem(index)}>✕</button>
              </div>
            </div>
          ))}
        </div>

        <div className="agc-actions">
          <button className="agc-btn" disabled={busy || !cleanItems().length} onClick={() => void runPreview()}>
            Preview composed body
          </button>
          <button
            className="agc-btn agc-btn-primary"
            disabled={busy || !draft.instruction_id.trim() || !draft.name.trim() || !cleanItems().length}
            onClick={() => void save()}
          >
            {draft.loaded ? `Save as v${draft.loaded.version + 1}` : 'Save v1'}
          </button>
        </div>

        {draft.loaded?.versions?.length ? (
          <section className="agc-versions">
            <h3>Versions</h3>
            {draft.loaded.versions.map((v) => (
              <div key={v.version} className="agc-version-row">
                <span className="agc-list-ref">instr:custom:{draft.loaded!.instruction_id}:{v.version}</span>
                <span>{v.status}</span>
                <span className="agc-muted">{v.created_by}{v.created_at ? ` · ${v.created_at}` : ''}</span>
                {v.status === 'active' ? (
                  <button
                    className="agc-btn agc-btn-danger"
                    disabled={busy}
                    onClick={() => void retire(`instr:custom:${draft.loaded!.instruction_id}:${v.version}`)}
                  >
                    Retire
                  </button>
                ) : null}
              </div>
            ))}
          </section>
        ) : null}

        {preview !== null ? (
          <section className="agc-preview">
            <h3>Composed body</h3>
            <pre>{preview || '(empty body)'}</pre>
          </section>
        ) : null}
      </main>
    </div>
  )
}
