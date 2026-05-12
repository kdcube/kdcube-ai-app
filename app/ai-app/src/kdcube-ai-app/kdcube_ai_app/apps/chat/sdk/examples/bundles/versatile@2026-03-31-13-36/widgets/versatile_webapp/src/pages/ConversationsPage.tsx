import { useState } from 'react';
import { assertOk, callOperation, conversationItems } from '../store/apiClient';
import type { ConversationsPayload } from '../store/types';
import { fmt } from './pageUtils';

interface ConversationsPageProps {
  conversations?: ConversationsPayload;
  reload: () => Promise<void>;
}

export function ConversationsPage({ conversations, reload }: ConversationsPageProps) {
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const items = conversationItems(conversations);

  async function mutate(operation: string, payload: Record<string, unknown>) {
    setBusy(true);
    setError('');
    try {
      const result = await callOperation<ConversationsPayload>(operation, payload);
      assertOk(result, 'Operation failed');
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Chats</h2>
          <p>{fmt(conversations?.telegram_user_id || conversations?.kdcube_user_id)} · {items.length} channels</p>
        </div>
        <button type="button" onClick={reload} disabled={busy}>Refresh</button>
      </div>
      {conversations?.error?.message && <div className="error">{conversations.error.message}</div>}
      {error && <div className="error">{error}</div>}
      <div className="inline-form">
        <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="New chat title" />
        <button
          type="button"
          className="primary"
          disabled={busy}
          onClick={() => {
            void mutate('conversations_create', { title });
            setTitle('');
          }}
        >
          Create
        </button>
      </div>
      <div className="grid-list">
        {items.map((item) => {
          const active = item.conversation_id === conversations?.active_conversation_id;
          return (
            <article className={`row-card ${active ? 'selected' : ''}`} key={item.conversation_id}>
              <strong>{item.title || item.conversation_id}</strong>
              <span>{item.conversation_id}</span>
              <div className="row-actions">
                <button type="button" disabled={busy || active} onClick={() => void mutate('conversations_switch', { conversation_id: item.conversation_id })}>
                  Use
                </button>
                <button type="button" disabled={busy} onClick={() => void mutate('conversations_delete', { conversation_id: item.conversation_id })}>
                  Delete
                </button>
              </div>
            </article>
          );
        })}
        {items.length === 0 && <div className="empty">No connected chats.</div>}
      </div>
    </section>
  );
}
