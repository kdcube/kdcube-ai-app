import { settings } from './settings';

function operationUrl(operation: string): string {
  const tenant = encodeURIComponent(settings.getTenant());
  const project = encodeURIComponent(settings.getProject());
  const bundleId = encodeURIComponent(settings.getBundleId());
  return `${settings.getBaseUrl()}/api/integrations/bundles/${tenant}/${project}/${bundleId}/operations/${operation}`;
}

export async function callOperation<T>(operation: string, payload: Record<string, unknown> = {}): Promise<T> {
  const response = await fetch(operationUrl(operation), {
    method: 'POST',
    credentials: 'include',
    headers: settings.authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ data: payload }),
  });
  const text = await response.text();
  let parsed: unknown = {};
  try {
    parsed = text ? JSON.parse(text) : {};
  } catch {
    parsed = { raw: text };
  }
  if (!response.ok) {
    const detail = typeof parsed === 'object' && parsed && 'detail' in parsed
      ? String((parsed as Record<string, unknown>).detail)
      : text || response.statusText;
    throw new Error(detail);
  }
  if (parsed && typeof parsed === 'object' && operation in parsed) {
    return (parsed as Record<string, unknown>)[operation] as T;
  }
  return parsed as T;
}
