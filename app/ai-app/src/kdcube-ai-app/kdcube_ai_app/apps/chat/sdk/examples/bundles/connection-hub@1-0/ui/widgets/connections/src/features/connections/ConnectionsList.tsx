import { useMemo } from 'react';
import { useAppSelector } from '../../app/hooks';
import { OAuthProviderSection } from './OAuthProviderSection';

// All connections-catalog OAuth providers (google, slack, …), sorted by label.
export function ConnectionsList() {
  const catalog = useAppSelector((s) => s.connections.catalog);
  const entries = useMemo(
    () => catalog.slice().sort((a, b) => (a.label || a.provider).localeCompare(b.label || b.provider)),
    [catalog],
  );
  return (
    <>
      {entries.map((entry) => (
        <OAuthProviderSection key={entry.provider} entry={entry} />
      ))}
    </>
  );
}
