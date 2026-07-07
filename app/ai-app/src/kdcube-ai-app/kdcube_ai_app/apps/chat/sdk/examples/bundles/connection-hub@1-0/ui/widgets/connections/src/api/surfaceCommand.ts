// Scene surface-command contract for this widget (`connections.hub.open`).
//
// A scene host that declares the contract forwards `kdcube.surface.command`
// postMessages whose `target_surface` names one of this widget's surfaces.
// The open payload rides in `ui_event` (the envelope scene hosts forward
// verbatim): `tab` plus the consent deep link's query params, carried as-is —
// `provider_id` / `connector_app_id` / `claims` / `account_id` for the
// delegated consent plan, `provider` / `tiers` / `account_id` for the
// provider-connections cards. The same keys are accepted at the message top
// level for hosts that relay the raw emitter message.
// The widget answers with `kdcube.surface.command.ack` (the usage-card idiom),
// echoing `command_id` when the command carries one.

export const SURFACE_COMMAND_MESSAGE_TYPE = 'kdcube.surface.command';
export const SURFACE_COMMAND_ACK_MESSAGE_TYPE = 'kdcube.surface.command.ack';

// Surfaces this widget answers for; scene contracts route by target_surface.
export const CONNECTIONS_TARGET_SURFACES = ['connection_hub.connections', 'connection_hub.settings'];

export interface ConnectionsHubOpenCommand {
  targetSurface: string;
  commandId: string;
  tab: string;
  /** The command's payload fields (`ui_event` minus `tab`), normalized to
   *  strings; list values arrive joined with commas — the same shape the
   *  widget's URL deep-link parsing reads. */
  params: Record<string, string>;
}

function paramValue(value: unknown): string {
  if (typeof value === 'string') return value.trim();
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean).join(',');
  }
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return '';
}

/** Split a comma/space-separated list param (e.g. `tiers`, `claims`). */
export function splitListParam(value: string): string[] {
  return String(value || '').split(/[\s,]+/).map((item) => item.trim()).filter(Boolean);
}

// Command-envelope keys; everything else in the payload is a deep-link param.
const ENVELOPE_KEYS = new Set([
  'type', 'tab', 'target_surface', 'targetSurface', 'action', 'command_id',
  'widget', 'source', 'surface_ref', 'object_ref', 'context', 'ui_event',
  'response', 'view', 'x', 'y', 'reason', 'ts',
]);

export function parseConnectionsHubOpen(data: unknown): ConnectionsHubOpenCommand | null {
  if (!data || typeof data !== 'object') return null;
  const raw = data as Record<string, unknown>;
  if (raw.type !== SURFACE_COMMAND_MESSAGE_TYPE) return null;
  const target = typeof raw.target_surface === 'string' ? raw.target_surface.trim().toLowerCase() : '';
  if (!CONNECTIONS_TARGET_SURFACES.includes(target)) return null;
  const action = typeof raw.action === 'string' ? raw.action.trim().toLowerCase() : '';
  if (action && action !== 'open') return null;
  const payload = (raw.ui_event && typeof raw.ui_event === 'object' ? raw.ui_event : raw) as Record<string, unknown>;
  const params: Record<string, string> = {};
  Object.entries(payload).forEach(([key, value]) => {
    const cleanKey = String(key || '').trim();
    if (!cleanKey || ENVELOPE_KEYS.has(cleanKey)) return;
    const cleanValue = paramValue(value);
    if (cleanValue) params[cleanKey] = cleanValue;
  });
  return {
    targetSurface: target,
    commandId: typeof raw.command_id === 'string' ? raw.command_id.trim() : '',
    tab: typeof payload.tab === 'string' ? payload.tab.trim() : '',
    params,
  };
}

export function ackConnectionsHubOpen(command: ConnectionsHubOpenCommand, reason: string): void {
  try {
    if (!window.parent || window.parent === window) return;
    const ack: Record<string, unknown> = {
      type: SURFACE_COMMAND_ACK_MESSAGE_TYPE,
      target_surface: command.targetSurface,
      action: 'open',
      reason,
      ts: new Date().toISOString(),
    };
    if (command.commandId) {
      ack.command_id = command.commandId;
      ack.ok = true;
    }
    window.parent.postMessage(ack, '*');
  } catch {
    // Host diagnostics are best-effort only.
  }
}
