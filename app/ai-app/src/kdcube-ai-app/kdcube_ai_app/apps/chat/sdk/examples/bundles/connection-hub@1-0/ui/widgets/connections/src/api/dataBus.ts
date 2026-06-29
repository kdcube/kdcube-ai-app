import { io, type Socket } from 'socket.io-client';
import { postPublicOp } from './client';
import { settings } from './settings';

interface FederatedClaimResult {
  ok?: boolean;
  federated_token?: string;
  session_id?: string;
  expires_at?: number;
  bundle_id?: string;
  error?: string;
  message?: string;
}

export interface ConnectionHubServiceEnvelope {
  type?: string;
  data?: Record<string, unknown>;
  event?: Record<string, unknown>;
  service?: Record<string, unknown>;
  conversation?: Record<string, unknown>;
}

type EventSubscriber = {
  onEvent: (event: ConnectionHubServiceEnvelope) => void;
  onError?: (error: Error) => void;
};

let socket: Socket | null = null;
let socketKey = '';
let sessionId = '';
let tokenExpiresAt = 0;
let connectPromise: Promise<void> | null = null;
let socketForPromise: Promise<{ socket: Socket; sessionId: string }> | null = null;
const subscribers = new Set<EventSubscriber>();

function trace(message: string, data: Record<string, unknown> = {}): void {
  console.info(`[connection-hub:data-bus] ${message}`, data);
}

async function claim(): Promise<{ token: string; sessionId: string; bundleId: string; expiresAt: number }> {
  trace('claim requested', {
    tenant: settings.getTenant(),
    project: settings.getProject(),
    bundleId: settings.getBundleId(),
  });
  const result = await postPublicOp<FederatedClaimResult>('federated_data_bus_claim', {});
  if (result.ok === false) {
    throw new Error(result.message || result.error || 'Connection Hub Data Bus claim failed');
  }
  const token = String(result.federated_token || '').trim();
  const sid = String(result.session_id || '').trim();
  const bundleId = String(result.bundle_id || settings.getBundleId()).trim();
  if (!token || !sid || !bundleId) {
    throw new Error('Connection Hub Data Bus claim did not return token, session, and bundle.');
  }
  trace('claim issued', { sessionId: sid, bundleId, expiresAt: result.expires_at || 0 });
  return { token, sessionId: sid, bundleId, expiresAt: Number(result.expires_at || 0) };
}

function reset(current: Socket): void {
  if (socket === current) {
    current.off('chat_service', dispatchServiceEvent);
    socket = null;
    socketKey = '';
    sessionId = '';
    tokenExpiresAt = 0;
    connectPromise = null;
  }
}

function dispatchServiceEvent(payload: unknown): void {
  if (!payload || typeof payload !== 'object') return;
  const event = payload as ConnectionHubServiceEnvelope;
  trace('service event received', {
    type: event.type || '',
    sessionId,
    subscriberCount: subscribers.size,
  });
  for (const subscriber of subscribers) {
    try {
      subscriber.onEvent(event);
    } catch (error) {
      subscriber.onError?.(error instanceof Error ? error : new Error(String(error)));
    }
  }
}

function bindServiceEvents(current: Socket): void {
  current.off('chat_service', dispatchServiceEvent);
  current.on('chat_service', dispatchServiceEvent);
}

function ensureConnected(current: Socket): Promise<void> {
  if (current.connected) return Promise.resolve();
  if (connectPromise) return connectPromise;
  connectPromise = new Promise<void>((resolve, reject) => {
    let timeout: number | undefined;
    const cleanup = () => {
      if (timeout !== undefined) window.clearTimeout(timeout);
      current.off('connect', onConnect);
      current.off('connect_error', onConnectError);
    };
    function onConnect() {
      cleanup();
      trace('socket connected', { socketId: current.id || '', sessionId });
      resolve();
    }
    function onConnectError(error: unknown) {
      cleanup();
      current.disconnect();
      reset(current);
      console.warn('[connection-hub:data-bus] socket connect_error', {
        message: error instanceof Error ? error.message : String(error),
      });
      reject(error instanceof Error ? error : new Error(String(error)));
    }
    timeout = window.setTimeout(() => {
      cleanup();
      current.disconnect();
      reset(current);
      reject(new Error('Timed out connecting Connection Hub live channel.'));
    }, 8000);
    current.once('connect', onConnect);
    current.once('connect_error', onConnectError);
    current.connect();
  }).finally(() => {
    connectPromise = null;
  });
  return connectPromise;
}

async function socketFor(): Promise<{ socket: Socket; sessionId: string }> {
  const now = Math.floor(Date.now() / 1000);
  if (socket && socketKey && sessionId && tokenExpiresAt > now + 30) {
    await ensureConnected(socket);
    return { socket, sessionId };
  }
  if (socketForPromise) return socketForPromise;
  socketForPromise = (async () => {
    const grant = await claim();
    const key = [
      settings.getBaseUrl(),
      settings.getTenant(),
      settings.getProject(),
      grant.bundleId,
      grant.sessionId,
    ].join('|');
    const auth = {
      tenant: settings.getTenant(),
      project: settings.getProject(),
      bundle_id: grant.bundleId,
      federated_token: grant.token,
    };
    tokenExpiresAt = grant.expiresAt;
    if (socket && socketKey === key) {
      socket.auth = auth;
      sessionId = grant.sessionId;
      bindServiceEvents(socket);
      await ensureConnected(socket);
      return { socket, sessionId };
    }
    if (socket) {
      socket.disconnect();
      reset(socket);
    }
    socket = io(settings.getBaseUrl(), {
      path: '/socket.io',
      transports: ['websocket'],
      upgrade: false,
      withCredentials: true,
      autoConnect: false,
      auth,
      reconnectionAttempts: 0,
    });
    socketKey = key;
    sessionId = grant.sessionId;
    bindServiceEvents(socket);
    trace('socket connecting', { baseUrl: settings.getBaseUrl(), sessionId, bundleId: grant.bundleId });
    await ensureConnected(socket);
    return { socket, sessionId };
  })().finally(() => {
    socketForPromise = null;
  });
  return socketForPromise;
}

export async function getConnectionHubLiveSessionId(): Promise<string> {
  const result = await socketFor();
  return result.sessionId;
}

export async function reconnectConnectionHubLiveChannel(): Promise<string> {
  if (socket) {
    socket.disconnect();
    reset(socket);
  }
  const result = await socketFor();
  return result.sessionId;
}

export function subscribeConnectionHubEvents(
  onEvent: (event: ConnectionHubServiceEnvelope) => void,
  onError?: (error: Error) => void,
): () => void {
  let closed = false;
  const subscriber = { onEvent, onError };
  subscribers.add(subscriber);

  void (async () => {
    try {
      const result = await socketFor();
      if (closed) return;
      bindServiceEvents(result.socket);
      trace('subscribed to chat_service', { sessionId: result.sessionId, subscriberCount: subscribers.size });
    } catch (error) {
      if (!closed) onError?.(error instanceof Error ? error : new Error(String(error)));
    }
  })();

  return () => {
    closed = true;
    subscribers.delete(subscriber);
  };
}
