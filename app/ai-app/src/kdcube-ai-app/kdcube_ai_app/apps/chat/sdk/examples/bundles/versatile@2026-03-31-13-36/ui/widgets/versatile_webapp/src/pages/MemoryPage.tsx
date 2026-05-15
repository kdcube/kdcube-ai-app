import { MemoriesWidgetEmbed } from '@kdcube/memory-widget';
import type { MemoryPayload } from '../store/types';

interface MemoryPageProps {
  memory?: MemoryPayload;
  reload: () => Promise<void>;
}

export function MemoryPage({ memory, reload }: MemoryPageProps) {
  const count = Number(memory?.count || memory?.memories?.length || 0);
  return (
    <section className="page page-wide memory-embed-page">
      <div className="page-header">
        <div>
          <h1>Memory</h1>
          <p>{count} durable notes · shared memory widget</p>
        </div>
        <div className="toolbar-actions">
          <button type="button" className="ghost-button" onClick={() => void reload()}>Refresh</button>
        </div>
      </div>
      {memory?.ok === false && (
        <div className="notice error">{memory.message || memory.error || 'Memory is unavailable.'}</div>
      )}
      <div className="memory-widget-direct">
        <MemoriesWidgetEmbed />
      </div>
    </section>
  );
}
