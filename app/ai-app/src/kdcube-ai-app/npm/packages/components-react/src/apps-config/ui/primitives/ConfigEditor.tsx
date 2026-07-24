/** Admin merge-patch editor for one app's stored props.
 *
 * The operator writes a partial JSON subtree; Apply MERGE-writes it through
 * the platform admin route (`set_bundle_props`, op=merge) and the panel
 * reloads the stored truth. Writes are admin-gated SERVER-SIDE; the change
 * lands live (the platform regenerates the runtime descriptor view), and the
 * descriptor file remains the restart-time source of truth. Hidden when the
 * data source is read-only.
 */
import { useState } from 'react';
import { useAppsConfigController } from '../../binding.tsx';

const PLACEHOLDER = `{
  "react": {
    "default_agent": {
      "instructions": { "tool_catalog_detail": "compact" }
    }
  }
}`;

export function ConfigEditor() {
  const controller = useAppsConfigController();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null);

  if (!controller.canEdit()) return null;

  const apply = async () => {
    let patch: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(text);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('the patch must be a JSON object');
      }
      patch = parsed as Record<string, unknown>;
    } catch (err) {
      setNotice({ tone: 'error', text: err instanceof Error ? err.message : String(err) });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      await controller.updateAppConfig(patch);
      setNotice({ tone: 'ok', text: 'Merged. The view shows the stored config.' });
      setText('');
    } catch (err) {
      setNotice({ tone: 'error', text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ac-config-editor">
      {notice && (
        <p className={`ac-note ${notice.tone === 'ok' ? 'ac-note--ok' : 'ac-note--error'}`}>
          {notice.text}
        </p>
      )}
      <textarea
        className="ac-config-editor__input"
        rows={8}
        spellCheck={false}
        placeholder={PLACEHOLDER}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="ac-config-editor__actions">
        <button
          type="button"
          className="ac-btn ac-btn--primary"
          disabled={busy || !text.trim()}
          onClick={() => void apply()}
        >
          Apply merge patch
        </button>
      </div>
    </div>
  );
}
